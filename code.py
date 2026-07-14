import tkinter as tk
import subprocess
import hashlib
import hmac
import os
import datetime
import ctypes

# ---------- Colors & Fonts ----------
BG_DARK = "#1e1e2e"
BG_PANEL = "#2a2a3d"
ACCENT_RED = "#e74c3c"
ACCENT_GREEN = "#2ecc71"
ACCENT_BLUE = "#3498db"
TEXT_LIGHT = "#f0f0f0"
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_NORMAL = ("Segoe UI", 11)
FONT_BUTTON = ("Segoe UI", 11, "bold")

# ---------- Lockout config ----------
MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 15

# ---------- Password hashing (PBKDF2-HMAC-SHA256, salted) ----------
PBKDF2_ITERATIONS = 260_000

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16)  # new random salt per user
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        PBKDF2_ITERATIONS
    )
    return salt, derived

def verify_password(password, salt, expected_hash):
    _, derived = hash_password(password, salt)
    return hmac.compare_digest(derived, expected_hash)

# ---------- User store ----------
# Each entry: username -> (salt, hash)
users = {
    "admin": hash_password("adminpass123"),
    "bhavya": hash_password("mypassword456")
}

# Tracks: username -> {"count": int, "last_failed": datetime}
failed_attempts = {}

def check_login(username, password):
    record = failed_attempts.get(username)

    # If locked, check whether the lockout window has expired
    if record and record["count"] >= MAX_ATTEMPTS:
        elapsed = datetime.datetime.now() - record["last_failed"]
        if elapsed < datetime.timedelta(minutes=LOCKOUT_MINUTES):
            remaining = LOCKOUT_MINUTES - int(elapsed.total_seconds() // 60)
            return "locked", remaining
        else:
            # Lockout window expired, reset the counter
            failed_attempts[username] = {"count": 0, "last_failed": None}

    if username in users:
        salt, expected_hash = users[username]
        if verify_password(password, salt, expected_hash):
            failed_attempts[username] = {"count": 0, "last_failed": None}
            return "success", None

    count = failed_attempts.get(username, {"count": 0})["count"] + 1
    failed_attempts[username] = {"count": count, "last_failed": datetime.datetime.now()}
    return "failed", None

# ---------- Logging ----------
def log_event(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("usb_security.log", "a") as f:
        f.write(f"[{timestamp}] {message}\n")

# ---------- Admin check ----------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

# ---------- Registry actions ----------
def run_reg_command(value, username, action_label):
    if not is_admin():
        log_event(f"{action_label} FAILED for '{username}': not running as Administrator")
        return False, "Not running as Administrator. Right-click and 'Run as administrator'."

    result = subprocess.run([
        "reg", "add",
        r"HKLM\SYSTEM\CurrentControlSet\Services\USBSTOR",
        "/v", "Start", "/t", "REG_DWORD", "/d", str(value), "/f"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        log_event(f"{action_label} SUCCESS by user '{username}'")
        return True, None
    else:
        error_detail = result.stderr.strip() or "Unknown registry error"
        log_event(f"{action_label} FAILED by user '{username}': {error_detail}")
        return False, error_detail

def disable_usb(username):
    success, error = run_reg_command(4, username, "USB DISABLE")
    if success:
        print("USB disabled")
    else:
        print(f"USB disable FAILED: {error}")
    return success, error

def enable_usb(username):
    success, error = run_reg_command(3, username, "USB ENABLE")
    if success:
        print("USB enabled")
    else:
        print(f"USB enable FAILED: {error}")
    return success, error

# ---------- Login popup ----------
def ask_login(action):
    def attempt_login():
        username = username_entry.get()
        password = password_entry.get()
        result, remaining = check_login(username, password)

        if result == "success":
            log_event(f"LOGIN SUCCESS: '{username}'")
            popup.destroy()
            if action == "disable":
                success, error = disable_usb(username)
            else:
                success, error = enable_usb(username)

            if not success:
                show_status_popup("Action Failed", error, ACCENT_RED)
            else:
                label = "USB Disabled" if action == "disable" else "USB Enabled"
                show_status_popup("Success", f"{label} successfully.", ACCENT_GREEN)

        elif result == "locked":
            result_label.config(
                text=f"Account locked. Try again in {remaining} min.",
                fg=ACCENT_RED
            )
            log_event(f"LOGIN BLOCKED (locked out): '{username}'")
        else:
            result_label.config(text="Wrong username or password", fg=ACCENT_RED)
            log_event(f"LOGIN FAILED: '{username}'")

    popup = tk.Toplevel(root)
    popup.title("Login Required")
    popup.geometry("300x280")
    popup.configure(bg=BG_PANEL)
    popup.iconphoto(False, logo_image)

    tk.Label(popup, text="Authentication Required", font=FONT_NORMAL,
             bg=BG_PANEL, fg=TEXT_LIGHT).pack(pady=(15, 10))

    tk.Label(popup, text="Username:", bg=BG_PANEL, fg=TEXT_LIGHT).pack()
    username_entry = tk.Entry(popup)
    username_entry.pack(pady=5)

    tk.Label(popup, text="Password:", bg=BG_PANEL, fg=TEXT_LIGHT).pack()
    password_entry = tk.Entry(popup, show="*")
    password_entry.pack(pady=5)

    login_btn = tk.Button(popup, text="Login", font=FONT_BUTTON,
                           bg=ACCENT_BLUE, fg="white", relief="flat",
                           activebackground="#2980b9",
                           command=attempt_login)
    login_btn.pack(pady=10, ipadx=10, ipady=3)

    result_label = tk.Label(popup, text="", bg=BG_PANEL, fg=ACCENT_RED)
    result_label.pack()

def show_status_popup(title, message, color):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.geometry("320x150")
    popup.configure(bg=BG_PANEL)
    popup.iconphoto(False, logo_image)

    tk.Label(popup, text=title, font=FONT_NORMAL, bg=BG_PANEL, fg=color).pack(pady=(20, 10))
    tk.Label(popup, text=message, font=FONT_NORMAL, bg=BG_PANEL, fg=TEXT_LIGHT,
             wraplength=280, justify="center").pack(pady=5)

    tk.Button(popup, text="OK", font=FONT_BUTTON, bg=ACCENT_BLUE, fg="white",
              relief="flat", command=popup.destroy).pack(pady=15, ipadx=10, ipady=3)

def add_hover(button, normal_color, hover_color):
    button.bind("<Enter>", lambda e: button.config(bg=hover_color))
    button.bind("<Leave>", lambda e: button.config(bg=normal_color))

# ---------- Main window (created but hidden at first) ----------
root = tk.Tk()
root.title("USB Physical Security")
root.geometry("420x400")
root.configure(bg=BG_DARK)
root.withdraw()  # hide main window until splash finishes

# Load the logo once, reuse everywhere
logo_image = tk.PhotoImage(file="usb_security_logo.png")
root.iconphoto(True, logo_image)

title_label = tk.Label(root, text="USB Physical Security Tool",
                        font=FONT_TITLE, bg=BG_DARK, fg=TEXT_LIGHT)
title_label.pack(pady=(30, 10))

subtitle_label = tk.Label(root, text="Protecting endpoints from USB-based threats",
                           font=FONT_NORMAL, bg=BG_DARK, fg="#aaaaaa")
subtitle_label.pack(pady=(0, 15))

# Warn in the UI if not running elevated, since reg edits will fail silently otherwise
if not is_admin():
    admin_warning = tk.Label(root, text="⚠ Not running as Administrator — actions will fail",
                              font=FONT_NORMAL, bg=BG_DARK, fg=ACCENT_RED,
                              wraplength=380, justify="center")
    admin_warning.pack(pady=(0, 5))

canvas = tk.Canvas(root, width=400, height=220, bg=BG_DARK, highlightthickness=0)
canvas.pack(pady=10)

faded_logo_img = tk.PhotoImage(file="logo_faded.png")

# Faded logo sits behind both buttons, centered
canvas.create_image(200, 110, image=faded_logo_img, anchor="center")

btn1 = tk.Button(root, text="Disable USB", font=FONT_BUTTON,
                  bg=ACCENT_RED, fg="white", relief="flat",
                  activebackground="#c0392b",
                  command=lambda: ask_login("disable"))
canvas.create_window(200, 60, window=btn1, anchor="center")
add_hover(btn1, ACCENT_RED, "#c0392b")

btn2 = tk.Button(root, text="Enable USB", font=FONT_BUTTON,
                  bg=ACCENT_GREEN, fg="white", relief="flat",
                  activebackground="#27ae60",
                  command=lambda: ask_login("enable"))
canvas.create_window(200, 160, window=btn2, anchor="center")
add_hover(btn2, ACCENT_GREEN, "#27ae60")

# ---------- Splash screen ----------
splash = tk.Toplevel()
splash.overrideredirect(True)  # removes title bar/borders for a clean splash look
splash.configure(bg=BG_DARK)

splash_width, splash_height = 300, 300
screen_width = splash.winfo_screenwidth()
screen_height = splash.winfo_screenheight()
x = (screen_width - splash_width) // 2
y = (screen_height - splash_height) // 2
splash.geometry(f"{splash_width}x{splash_height}+{x}+{y}")

splash_logo = tk.Label(splash, image=logo_image, bg=BG_DARK)
splash_logo.pack(pady=(30, 10))

splash_text = tk.Label(splash, text="USB Physical Security",
                        font=FONT_TITLE, bg=BG_DARK, fg=TEXT_LIGHT)
splash_text.pack()

def close_splash():
    splash.destroy()
    root.deiconify()  # show the main window now

root.after(2000, close_splash)  # after 2 seconds, close splash and show main app

root.mainloop()