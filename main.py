import sys
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ListProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.storage.jsonstore import JsonStore
from kivy.core.window import Window
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from plyer import notification
from functools import partial
import csv
import os
import datetime
from collections import defaultdict
from kivy.utils import platform, get_color_from_hex
import re
import hashlib
import holidays
from kivy.clock import Clock
import locale
import traceback

# Set locale for currency and date formatting
try:
    locale.setlocale(locale.LC_ALL, '')
    CURRENCY_SYMBOL = locale.currency(0).strip('0.00') or '$'
except:
    CURRENCY_SYMBOL = '$'

# Set window size for testing (optional, remove for mobile)
# Window.size = (360, 640)  # Commented out for full screen on mobile

# Data storage
STORE_FILE = "bills_store.json"
store = JsonStore(STORE_FILE)
DEFAULT_PIN = "1234"

# UK bank holidays
current_year = datetime.datetime.now().year
uk_holidays = holidays.UnitedKingdom(years=range(current_year, current_year + 10))
BANK_HOLIDAYS = [d.strftime('%d/%m') for d in uk_holidays]

# Bill categories and icons
BILL_CATEGORIES = {
    'Utilities': '⚡',
    'Rent': '🏠',
    'Subscriptions': '📺',
    'Insurance': '🛡️',
    'Groceries': '🛒',
    'Other': '💸'
}

# Robust crash logging function
def log_crash(e, source="Unknown"):
    try:
        print(f"[CRASH] Logging crash from {source}: {str(e)}")
        save_dirs = []
        if platform == 'android':
            try:
                from jnius import autoclass
                Environment = autoclass('android.os.Environment')
                save_dirs.append(os.path.join(
                    Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS).getPath(),
                    'BillsManager_Logs'
                ))
                print(f"[CRASH] Android primary save_dir: {save_dirs[-1]}")
            except Exception as jnius_error:
                print(f"[CRASH] jnius error: {str(jnius_error)}")
            save_dirs.append(os.path.join(os.path.expanduser('~'), 'BillsManager_Logs'))
            print(f"[CRASH] Android fallback save_dir: {save_dirs[-1]}")
        else:
            save_dirs.append(os.path.expanduser('~/Desktop'))
            print(f"[CRASH] Desktop save_dir: {save_dirs[-1]}")
        save_dirs.append(os.getcwd())
        print(f"[CRASH] CWD fallback save_dir: {save_dirs[-1]}")

        log_file = None
        for save_dir in save_dirs:
            try:
                os.makedirs(save_dir, exist_ok=True)
                print(f"[CRASH] Created/verified directory: {save_dir}")
                log_file = os.path.join(save_dir, 'bills_manager_crash.log')
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n--- Crash Report: {datetime.datetime.now()} (Source: {source}) ---\n")
                    f.write(f"Exception: {str(e)}\n")
                    f.write("Stack Trace:\n")
                    f.write(traceback.format_exc())
                    f.write("\n" + "-"*50 + "\n")
                print(f"[CRASH] Successfully wrote to {log_file}")
                return
            except Exception as log_error:
                print(f"[CRASH] Failed to write to {save_dir}: {str(log_error)}")
                continue

        print(f"[CRASH] All logging attempts failed. Exception: {str(e)}")
        print(f"[CRASH] Stack Trace:\n{traceback.format_exc()}")
    except Exception as log_error:
        print(f"[CRASH] Fatal error in log_crash: {str(log_error)}")

# Global exception handler
def global_exception_handler(exc_type, exc_value, exc_traceback):
    try:
        print(f"[CRASH] Unhandled exception caught: {exc_type.__name__}: {str(exc_value)}")
        log_crash(exc_value, source="Global Exception Handler")
    except Exception as handler_error:
        print(f"[CRASH] Error in global exception handler: {str(handler_error)}")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = global_exception_handler

# Kivy Layout String with theme support
KV = '''
#:import C kivy.utils.get_color_from_hex

ScreenManager:
    LoginScreen:
    MainScreen:
    SummaryScreen:

<LoginScreen>:
    name: 'login'
    FloatLayout:
        canvas.before:
            Color:
                rgba: C('#1A2E4B') if app.theme == 'dark' else C('#E6F0FA')
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: C('#2E4A7D') if app.theme == 'dark' else C('#A3CFFA')
            Rectangle:
                pos: self.x, self.y + self.height * 0.5
                size: self.width, self.height * 0.5
        BoxLayout:
            orientation: 'vertical'
            spacing: 20
            padding: 30
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            size_hint: 0.9, 0.6
            canvas.before:
                Color:
                    rgba: C('#FFFFFF1A') if app.theme == 'dark' else C('#0000001A')
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [20]
            Label:
                text: "Bill Manager"
                font_size: '30sp'
                bold: True
                color: C('#FFD700') if app.theme == 'dark' else C('#FF8C00')
            TextInput:
                id: pin_input
                password: True
                multiline: False
                font_size: '20sp'
                hint_text: 'Enter 4-digit PIN'
                background_color: C('#FFFFFF1A') if app.theme == 'dark' else C('#0000001A')
                foreground_color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
            Button:
                text: 'Unlock'
                font_size: '18sp'
                background_normal: ''
                background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                on_release: root.validate_pin(pin_input.text)
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]
            Button:
                text: 'Change PIN'
                font_size: '18sp'
                background_normal: ''
                background_color: C('#994433') if app.theme == 'dark' else C('#CC8866')
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                on_release: root.open_change_pin_popup()
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]
            Button:
                text: 'Toggle Theme'
                font_size: '18sp'
                background_normal: ''
                background_color: C('#555555') if app.theme == 'dark' else C('#AAAAAA')
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                on_release: app.switch_theme()
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]
            Button:
                text: 'Test Crash'
                font_size: '18sp'
                background_normal: ''
                background_color: C('#FF4444') if app.theme == 'dark' else C('#FF6666')
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                on_release: root.test_crash()
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]

<MainScreen>:
    name: 'main'
    FloatLayout:
        canvas.before:
            Color:
                rgba: C('#1A2E4B') if app.theme == 'dark' else C('#E6F0FA')
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: C('#2E4A7D') if app.theme == 'dark' else C('#A3CFFA')
            Rectangle:
                pos: self.x, self.y + self.height * 0.5
                size: self.width, self.height * 0.5
        BoxLayout:
            orientation: 'vertical'
            padding: 10
            spacing: 10
            BoxLayout:
                size_hint_y: None
                height: 50
                spacing: 10
                TextInput:
                    id: search
                    hint_text: 'Search bills...'
                    multiline: False
                    font_size: '16sp'
                    background_color: C('#FFFFFF1A') if app.theme == 'dark' else C('#0000001A')
                    foreground_color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_text: root.filter_bills(self.text)
                Button:
                    text: 'Clear'
                    size_hint_x: 0.3
                    background_normal: ''
                    background_color: C('#994433') if app.theme == 'dark' else C('#CC8866')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.clear_search()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
            BoxLayout:
                size_hint_y: None
                height: 50
                spacing: 10
                Button:
                    text: 'Sort: Name'
                    id: sort_name
                    background_normal: ''
                    background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.sort_bills('name')
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
                Button:
                    text: 'Sort: Amount'
                    id: sort_amount
                    background_normal: ''
                    background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.sort_bills('amount')
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
                Button:
                    text: 'Sort: Due'
                    id: sort_due
                    background_normal: ''
                    background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.sort_bills('due')
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
            RecycleView:
                id: rv
                viewclass: 'SelectableLabel'
                RecycleBoxLayout:
                    default_size: None, 50
                    default_size_hint: 1, None
                    size_hint_y: None
                    height: self.minimum_height
                    orientation: 'vertical'
                    spacing: 5
            Label:
                id: remaining
                text: f"Remaining to Pay: {app.currency_symbol}0.00"
                font_size: '18sp'
                color: C('#FFD700') if app.theme == 'dark' else C('#FF8C00')
                size_hint_y: None
                height: 40
            BoxLayout:
                size_hint_y: None
                height: 60
                spacing: 10
                Button:
                    text: 'Add Bill'
                    font_size: '18sp'
                    background_normal: ''
                    background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.open_add_popup()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
                Button:
                    text: 'Summary'
                    font_size: '18sp'
                    background_normal: ''
                    background_color: C('#994433') if app.theme == 'dark' else C('#CC8866')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.manager.current = 'summary'
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
                Button:
                    text: 'Backup'
                    font_size: '18sp'
                    background_normal: ''
                    background_color: C('#669933') if app.theme == 'dark' else C('#99CC66')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.backup_bills()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]
                Button:
                    text: 'Import'
                    font_size: '18sp'
                    background_normal: ''
                    background_color: C('#555555') if app.theme == 'dark' else C('#AAAAAA')
                    color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                    on_release: root.import_bills()
                    canvas.before:
                        Color:
                            rgba: self.background_color
                        RoundedRectangle:
                            pos: self.pos
                            size: self.size
                            radius: [10]

<SummaryScreen>:
    name: 'summary'
    FloatLayout:
        canvas.before:
            Color:
                rgba: C('#1A2E4B') if app.theme == 'dark' else C('#E6F0FA')
            Rectangle:
                pos: self.pos
                size: self.size
            Color:
                rgba: C('#2E4A7D') if app.theme == 'dark' else C('#A3CFFA')
            Rectangle:
                pos: self.x, self.y + self.height * 0.5
                size: self.width, self.height * 0.5
        BoxLayout:
            orientation: 'vertical'
            padding: 10
            spacing: 10
            pos_hint: {'center_x': 0.5, 'center_y': 0.5}
            size_hint: 0.9, 0.9
            Label:
                text: "Financial Summary"
                font_size: '24sp'
                bold: True
                color: C('#FFD700') if app.theme == 'dark' else C('#FF8C00')
            Label:
                id: total_paid
                text: f"Total Paid: {app.currency_symbol}0.00"
                font_size: '18sp'
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
            Label:
                id: total_remaining
                text: f"Total Remaining: {app.currency_symbol}0.00"
                font_size: '18sp'
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
            Label:
                id: overdue
                text: f"Overdue: {app.currency_symbol}0.00"
                font_size: '18sp'
                color: C('#FF6666') if app.theme == 'dark' else C('#CC3333')
            BoxLayout:
                id: chart_container
                size_hint_y: None
                height: 200
            Button:
                text: 'Back to Bills'
                size_hint_y: None
                height: 50
                background_normal: ''
                background_color: C('#339999') if app.theme == 'dark' else C('#66CCCC')
                color: C('#FFFFFF') if app.theme == 'dark' else C('#000000')
                on_release: root.manager.current = 'main'
                canvas.before:
                    Color:
                        rgba: self.background_color
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [10]

<SelectableLabel@ButtonBehavior+Label>:
    background_color: (0.5, 0.5, 0.5, 1) if not hasattr(self, 'background_color') else self.background_color
    color: (1, 1, 1, 1)
    canvas.before:
        Color:
            rgba: self.background_color if self.background_color else (0.5, 0.5, 0.5, 1)
        Rectangle:
            pos: self.pos
            size: self.size
'''

class LoginScreen(Screen):
    failed_attempts = 0
    lockout_until = 0
    
    def validate_pin(self, pin):
        try:
            import time
            now = time.time()
            if now < self.lockout_until:
                remaining = int(self.lockout_until - now)
                self.notify("Locked Out", f"Too many failed attempts. Try again in {remaining} seconds.")
                return

            if not pin.isdigit() or len(pin) != 4:
                self.ids.pin_input.text = ''
                self.ids.pin_input.hint_text = 'Enter a 4-digit PIN'
                return

            stored_pin = store.get('pin')['value'] if store.exists('pin') else hashlib.sha256(DEFAULT_PIN.encode()).hexdigest()
            hashed_pin = hashlib.sha256(pin.encode()).hexdigest()

            if hashed_pin == stored_pin:
                self.failed_attempts = 0
                if hashed_pin == hashlib.sha256(DEFAULT_PIN.encode()).hexdigest():
                    self.notify("Notice", "You're using the default PIN. It's recommended to change it.")
                    self.open_change_pin_popup()
                else:
                    self.manager.current = 'main'
            else:
                self.failed_attempts += 1
                self.ids.pin_input.text = ''
                self.ids.pin_input.hint_text = 'Incorrect PIN. Try again.'
                if self.failed_attempts % 5 == 0:
                    penalty_time = 60 * (self.failed_attempts // 5)
                    self.lockout_until = now + penalty_time
                    self.notify("Too Many Attempts", f"Locked for {penalty_time} seconds.")
        except Exception as e:
            self.notify("Error", f"Failed to validate PIN: {str(e)}")
            log_crash(e, source="validate_pin")

    def open_change_pin_popup(self):
        try:
            content = BoxLayout(orientation='vertical', spacing=10, padding=10)
            current_pin = TextInput(hint_text="Current PIN", password=True, multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            new_pin = TextInput(hint_text="New PIN (4 digits)", password=True, multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            confirm_pin = TextInput(hint_text="Confirm New PIN", password=True, multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            save_btn = Button(text="Save", size_hint_y=None, height=40, background_normal='', background_color=(0.2, 0.7, 0.7, 1))
            error_label = Label(text="", color=(1, 0.4, 0.4, 1))

            content.add_widget(current_pin)
            content.add_widget(new_pin)
            content.add_widget(confirm_pin)
            content.add_widget(save_btn)
            content.add_widget(error_label)

            popup = Popup(title="Change PIN", content=content, size_hint=(0.8, 0.6))

            def save_pin(*args):
                try:
                    stored_pin = store.get('pin')['value'] if store.exists('pin') else hashlib.sha256(DEFAULT_PIN.encode()).hexdigest()
                    if hashlib.sha256(current_pin.text.encode()).hexdigest() != stored_pin:
                        error_label.text = "Incorrect current PIN"
                        return
                    if not (new_pin.text.isdigit() and len(new_pin.text) == 4):
                        error_label.text = "New PIN must be 4 digits"
                        return
                    if new_pin.text != confirm_pin.text:
                        error_label.text = "PINs do not match"
                        return
                    store.put('pin', value=hashlib.sha256(new_pin.text.encode()).hexdigest())
                    popup.dismiss()
                    self.notify("PIN Changed", "Your PIN has been updated")
                    self.manager.current = 'main'
                except Exception as e:
                    error_label.text = f"Error: {str(e)}"
                    log_crash(e, source="save_pin")

            save_btn.bind(on_release=save_pin)
            popup.open()
        except Exception as e:
            self.notify("Error", f"Failed to open change PIN popup: {str(e)}")
            log_crash(e, source="open_change_pin_popup")

    def notify(self, title, message):
        try:
            notification.notify(title=title, message=message, timeout=5)
        except Exception as e:
            print(f"[ERROR] Notification failed: {str(e)}")
            self.show_toast(message)

    def show_toast(self, message):
        try:
            toast = Popup(
                title='',
                content=Label(text=message, color=(1, 1, 1, 1)),
                size_hint=(0.8, 0.2),
                pos_hint={'center_x': 0.5, 'top': 0.9},
                auto_dismiss=True
            )
            toast.open()
            Clock.schedule_once(lambda dt: toast.dismiss(), 2)
        except Exception as e:
            print(f"[ERROR] Toast failed: {str(e)}")
            log_crash(e, source="show_toast")

    def test_crash(self):
        try:
            dummy_dict = {}
            print(dummy_dict['nonexistent_key'])
        except Exception as e:
            self.notify("Test Crash", f"Triggered test crash: {str(e)}")
            log_crash(e, source="test_crash")

class MainScreen(Screen):
    bills = ListProperty([])
    sort_key = 'due'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.notification_callbacks = []

    def on_enter(self):
        try:
            self.expanded_months = set()
            today = datetime.datetime.now()
            current_month = today.strftime('%B')
            self.expanded_months.add(current_month)
            if today.day >= 25:
                next_month = (today.replace(day=28) + datetime.timedelta(days=4)).strftime('%B')
                self.expanded_months.add(next_month)
            self.load_bills()
            self.update_view()
            self.schedule_notifications()
        except Exception as e:
            self.notify("Error", f"Failed to initialize screen: {str(e)}")
            log_crash(e, source="on_enter")

    def load_bills(self):
        try:
            if store.exists('bills'):
                valid_bills = []
                for b in store.get('bills')['data']:
                    if not all(k in b for k in ['name', 'amount', 'due', 'paid', 'category']):
                        self.notify("Data Warning", f"Discarded invalid bill: {b.get('name', 'Unknown')}")
                        continue
                    if not isinstance(b['amount'], (int, float)) or not isinstance(b['due'], str):
                        self.notify("Data Warning", f"Discarded invalid bill: {b.get('name', 'Unknown')}")
                        continue
                    if not re.match(r'^\d{2}/\d{2}/\d{4}$', b['due']):
                        self.notify("Data Warning", f"Discarded invalid bill date: {b.get('name', 'Unknown')}")
                        continue
                    try:
                        datetime.datetime.strptime(b['due'], '%d/%m/%Y')
                        valid_bills.append(b)
                    except ValueError:
                        self.notify("Data Warning", f"Discarded invalid bill date: {b.get('name', 'Unknown')}")
                self.bills = valid_bills
            else:
                self.bills = []
        except Exception as e:
            self.notify("Error", f"Failed to load bills: {str(e)}")
            self.bills = []
            store.delete('bills')
            log_crash(e, source="load_bills")

    def save_bills(self):
        try:
            store.put('bills', data=self.bills)
        except Exception as e:
            self.notify("Error", f"Failed to save bills: {str(e)}")
            log_crash(e, source="save_bills")

    def update_view(self):
        try:
            print(f"[DEBUG] Updating view with {len(self.bills)} bills, sort_key: {self.sort_key}")
            self.ids.rv.data = []
            search_text = self.ids.search.text.lower()
            today = datetime.datetime.now()
            valid_bills = []

            for b in self.bills:
                if not all(k in b for k in ['name', 'amount', 'due', 'paid', 'category']):
                    self.notify("Data Warning", f"Skipping invalid bill: {b.get('name', 'Unknown')}")
                    continue
                try:
                    datetime.datetime.strptime(b['due'], '%d/%m/%Y')
                    valid_bills.append(b)
                except ValueError:
                    self.notify("Data Warning", f"Skipping bill with invalid date: {b.get('name', 'Unknown')}")
                    continue

            filtered_bills = [
                b for b in valid_bills
                if (search_text in b['name'].lower() or
                    search_text in str(b['amount']).lower() or
                    search_text in b['due'].lower() or
                    search_text in b.get('frequency', '').lower() or
                    search_text in b['category'].lower())
            ]

            sort_functions = {
                'name': lambda x: x['name'].lower(),
                'amount': lambda x: float(x['amount']),
                'due': lambda x: datetime.datetime.strptime(x['due'], '%d/%m/%Y')
            }
            sorted_bills = sorted(filtered_bills, key=sort_functions[self.sort_key])

            grouped = defaultdict(list)
            for b in sorted_bills:
                try:
                    month = datetime.datetime.strptime(b['due'], '%d/%m/%Y').strftime('%B')
                    grouped[month].append(b)
                except ValueError:
                    self.notify("Data Warning", f"Invalid due date for bill: {b['name']}")
                    continue

            for month, bills in grouped.items():
                total = sum(float(b['amount']) for b in bills)
                color = self.month_color(month)
                is_expanded = month in self.expanded_months

                self.ids.rv.data.append({
                    'text': f"▶ {month.upper()} (Tap to Expand)" if not is_expanded else f"▼ {month.upper()} (Total: {App.get_running_app().currency_symbol}{total:.2f})",
                    'on_release': partial(self.toggle_month, month),
                    'background_color': color,
                    'color': (1, 1, 1, 1),
                    'font_size': '18sp'
                })

                if is_expanded:
                    for b in bills:
                        due_date = datetime.datetime.strptime(b['due'], '%d/%m/%Y')
                        is_overdue = due_date < today and not b['paid']
                        icon = BILL_CATEGORIES.get(b['category'], '💸')
                        self.ids.rv.data.append({
                            'text': f"{icon} {b['name']}: {App.get_running_app().currency_symbol}{b['amount']} (Due: {b['due']}){' ✓' if b['paid'] else ' ⚠' if is_overdue else ''}",
                            'on_release': partial(self.edit_bill, b),
                            'background_color': (0.3, 0.7, 0.3, 1) if b['paid'] else (1, 0.4, 0.4, 1) if is_overdue else (1, 1, 1, 1),
                            'color': (1, 1, 1, 1),
                            'font_size': '16sp',
                            'on_press': lambda *args, b=b: self.animate_button(args[0] if args else None)
                        })

            if not self.ids.rv.data:
                self.ids.rv.data = [{
                    'text': 'No bills found. Tap "Add Bill" to start.',
                    'on_release': lambda x: None,
                    'background_color': (0.5, 0.5, 0.5, 1),
                    'color': (1, 1, 1, 1),
                    'font_size': '16sp'
                }]

            remaining = sum(float(b['amount']) for b in valid_bills if not b['paid'])
            self.ids.remaining.text = f"Remaining to Pay: {App.get_running_app().currency_symbol}{remaining:.2f}"

            self.ids.rv.data = self.ids.rv.data
            self.ids.rv.refresh_from_data()
            print(f"[DEBUG] RV data set with {len(self.ids.rv.data)} items")
        except Exception as e:
            self.notify("Error", f"Failed to update view: {str(e)}")
            log_crash(e, source="update_view")

    def animate_button(self, instance):
        try:
            if instance and hasattr(instance, 'background_color'):
                anim = Animation(background_color=(0.5, 0.8, 0.8, 1), duration=0.1) + Animation(background_color=instance.background_color, duration=0.1)
                anim.start(instance)
        except Exception as e:
            self.notify("Error", f"Failed to animate button: {str(e)}")
            log_crash(e, source="animate_button")

    def month_color(self, month):
        colors = {
            'January': (0.4, 0.6, 0.9, 1), 'February': (0.8, 0.4, 0.7, 1),
            'March': (0.4, 0.9, 0.5, 1), 'April': (0.9, 0.6, 0.4, 1),
            'May': (0.9, 0.9, 0.4, 1), 'June': (0.4, 0.9, 0.9, 1),
            'July': (0.9, 0.4, 0.4, 1), 'August': (0.4, 0.9, 0.4, 1),
            'September': (0.6, 0.6, 0.9, 1), 'October': (0.9, 0.6, 0.9, 1),
            'November': (0.6, 0.9, 0.9, 1), 'December': (0.9, 0.6, 0.6, 1)
        }
        return colors.get(month, (0.5, 0.5, 0.5, 1))

    def toggle_month(self, month):
        try:
            print(f"[DEBUG] Toggling month: {month}, Current expanded: {self.expanded_months}")
            if month in self.expanded_months:
                self.expanded_months.remove(month)
            else:
                self.expanded_months.add(month)
            print(f"[DEBUG] After toggle, expanded: {self.expanded_months}")
            self.update_view()
        except Exception as e:
            self.notify("Error", f"Failed to toggle month: {str(e)}")
            log_crash(e, source="toggle_month")

    def clear_search(self):
        try:
            self.ids.search.text = ''
            self.update_view()
        except Exception as e:
            self.notify("Error", f"Failed to clear search: {str(e)}")
            log_crash(e, source="clear_search")

    def sort_bills(self, key):
        try:
            self.sort_key = key
            self.update_view()
            for btn in [self.ids.sort_name, self.ids.sort_amount, self.ids.sort_due]:
                btn.background_color = (0.2, 0.7, 0.7, 1) if btn is self.ids[f'sort_{key}'] else (0.5, 0.5, 0.5, 1)
        except Exception as e:
            self.notify("Error", f"Failed to sort bills: {str(e)}")
            log_crash(e, source="sort_bills")

    def open_add_popup(self):
        try:
            self.open_bill_popup()
        except Exception as e:
            self.notify("Error", f"Failed to open add popup: {str(e)}")
            log_crash(e, source="open_add_popup")

    def edit_bill(self, bill):
        try:
            self.open_bill_popup(bill)
        except Exception as e:
            self.notify("Error", f"Failed to open edit popup: {str(e)}")
            log_crash(e, source="edit_bill")

    def open_bill_popup(self, bill=None):
        try:
            is_edit = bill is not None
            content = BoxLayout(orientation='vertical', spacing=10, padding=10)
            name_input = TextInput(text=bill['name'] if is_edit else '', hint_text="Bill Name", multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            amount_input = TextInput(text=str(bill['amount']) if is_edit else '', hint_text="Amount", input_filter='float', multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            due_input = TextInput(text=bill['due'] if is_edit else '', hint_text="Due Date (DD/MM/YYYY)", multiline=False, background_color=(1, 1, 1, 0.1), foreground_color=(1, 1, 1, 1))
            category_input = Spinner(
                text=bill.get('category', 'Select Category') if is_edit else 'Select Category',
                values=list(BILL_CATEGORIES.keys()),
                size_hint_y=None,
                height=40,
                background_color=(0.2, 0.7, 0.7, 1)
            )
            freq_input = Spinner(
                text=bill.get('frequency', 'Select Frequency') if is_edit else 'Select Frequency',
                values=('Weekly', '4 Weekly', 'Monthly', 'Custom'),
                size_hint_y=None,
                height=40,
                background_color=(0.2, 0.7, 0.7, 1)
            )
            error_label = Label(text="", color=(1, 0.4, 0.4, 1))

            def autoformat_date(instance, value):
                try:
                    v = ''.join(c for c in value if c.isdigit())[:8]
                    new_text = ''
                    if v:
                        new_text += v[:2]
                        if len(v) > 2:
                            new_text += '/' + v[2:4]
                        if len(v) > 4:
                            new_text += '/' + v[4:]
                    instance.text = new_text
                    if len(new_text) == 10:
                        try:
                            datetime.datetime.strptime(new_text, '%d/%m/%Y')
                            error_label.text = ""
                        except ValueError:
                            error_label.text = "Invalid date"
                except Exception as e:
                    error_label.text = f"Error: {str(e)}"
                    log_crash(e, source="autoformat_date")

            due_input.bind(text=autoformat_date)

            save_btn = Button(text="Save", size_hint_y=None, height=40, background_normal='', background_color=(0.2, 0.7, 0.7, 1))
            complete_btn = Button(
                text=("Mark as Unpaid" if bill and bill.get('paid') else "Mark as Paid"),
                size_hint_y=None, height=40, background_normal='', background_color=(0.3, 0.7, 0.3, 1)
            )
            if is_edit:
                del_btn = Button(text="Delete", size_hint_y=None, height=40, background_normal='', background_color=(1, 0.4, 0.4, 1))

            content.add_widget(name_input)
            content.add_widget(amount_input)
            content.add_widget(due_input)
            content.add_widget(category_input)
            content.add_widget(freq_input)
            content.add_widget(error_label)
            content.add_widget(save_btn)
            content.add_widget(complete_btn)
            if is_edit:
                content.add_widget(del_btn)

            popup = Popup(title="Edit Bill" if is_edit else "Add Bill", content=content, size_hint=(0.9, 0.9))
            save_btn.bind(on_release=lambda x: self.save_bill(name_input.text, amount_input.text, due_input.text, category_input.text, freq_input.text, popup, error_label, bill))
            complete_btn.bind(on_release=lambda x: self.mark_bill_paid(bill, popup))
            if is_edit:
                del_btn.bind(on_release=lambda x: self.confirm_delete(bill, popup))
            popup.open()
        except Exception as e:
            self.notify("Error", f"Failed to open bill popup: {str(e)}")
            log_crash(e, source="open_bill_popup")

    def save_bill(self, name, amount, due, category, frequency, popup, error_label, bill=None):
        try:
            print(f"[DEBUG] Saving bill: {name}, amount: {amount}, due: {due}")
            if not name.strip():
                error_label.text = "Bill name cannot be empty"
                return
            try:
                amount_float = float(amount)
                if amount_float <= 0:
                    raise ValueError
            except ValueError:
                error_label.text = "Amount must be a positive number"
                return
            if not re.match(r'^\d{2}/\d{2}/\d{4}$', due):
                error_label.text = "Invalid date format (use DD/MM/YYYY)"
                return
            try:
                due_date = datetime.datetime.strptime(due, '%d/%m/%Y')
                if due_date.year < datetime.datetime.now().year - 1 or due_date.year > datetime.datetime.now().year + 10:
                    raise ValueError
            except ValueError:
                error_label.text = "Invalid or unrealistic date"
                return
            if category == 'Select Category':
                error_label.text = "Please select a category"
                return
            if frequency == 'Select Frequency':
                error_label.text = "Please select a frequency"
                return

            if bill is None:
                if frequency == 'Weekly':
                    due_date += datetime.timedelta(weeks=1)
                elif frequency == '4 Weekly':
                    due_date += datetime.timedelta(weeks=4)
                elif frequency == 'Monthly':
                    month = due_date.month + 1 if due_date.month < 12 else 1
                    year = due_date.year + 1 if month == 1 else due_date.year
                    try:
                        due_date = due_date.replace(month=month, year=year)
                    except ValueError:
                        due_date = due_date.replace(day=28, month=month, year=year)

            while due_date.weekday() >= 5 or due_date.strftime('%d/%m') in BANK_HOLIDAYS:
                due_date += datetime.timedelta(days=1)

            due_formatted = due_date.strftime('%d/%m/%Y')

            if bill:
                bill['name'] = name
                bill['amount'] = amount_float
                bill['due'] = due_formatted
                bill['category'] = category
                bill['frequency'] = frequency
            else:
                self.bills.append({
                    'name': name,
                    'amount': amount_float,
                    'paid': False,
                    'due': due_formatted,
                    'category': category,
                    'frequency': frequency
                })

            self.save_bills()
            self.update_view()
            self.schedule_notifications()
            popup.dismiss()
            self.notify("Bill Saved", f"{'Updated' if bill else 'Added'} {name}")
        except Exception as e:
            error_label.text = f"Error: {str(e)}"
            self.notify("Error", f"Failed to save bill: {str(e)}")
            log_crash(e, source="save_bill")

    def mark_bill_paid(self, bill, popup):
        try:
            if bill:
                bill['paid'] = not bill['paid']
                if bill['paid'] and bill['frequency'] != 'Custom':
                    try:
                        due_date = datetime.datetime.strptime(bill['due'], '%d/%m/%Y')
                        if bill['frequency'] == 'Weekly':
                            due_date += datetime.timedelta(weeks=1)
                        elif bill['frequency'] == '4 Weekly':
                            due_date += datetime.timedelta(weeks=4)
                        elif bill['frequency'] == 'Monthly':
                            month = due_date.month + 1 if due_date.month < 12 else 1
                            year = due_date.year + 1 if month == 1 else due_date.year
                            try:
                                due_date = due_date.replace(month=month, year=year)
                            except ValueError:
                                due_date = due_date.replace(day=28, month=month, year=year)
                        while due_date.weekday() >= 5 or due_date.strftime('%d/%m') in BANK_HOLIDAYS:
                            due_date += datetime.timedelta(days=1)
                        new_bill = bill.copy()
                        new_bill['due'] = due_date.strftime('%d/%m/%Y')
                        new_bill['paid'] = False
                        self.bills.append(new_bill)
                        self.notify("Bill Added", f"Next {bill['name']} due on {new_bill['due']}")
                    except Exception as e:
                        self.notify("Error", f"Failed to create next bill: {str(e)}")
                        log_crash(e, source="mark_bill_paid_next")
                self.save_bills()
                self.update_view()
                self.schedule_notifications()
                popup.dismiss()
                self.notify("Bill Updated", f"{bill['name']} marked as {'paid' if bill['paid'] else 'unpaid'}")
        except Exception as e:
            self.notify("Error", f"Failed to mark bill paid: {str(e)}")
            log_crash(e, source="mark_bill_paid")

    def confirm_delete(self, bill, popup):
        try:
            content = BoxLayout(orientation='vertical', spacing=10, padding=10)
            content.add_widget(Label(text=f"Delete '{bill['name']}'? This cannot be undone."))
            confirm_btn = Button(text="Delete", size_hint_y=None, height=40, background_normal='', background_color=(1, 0.4, 0.4, 1))
            cancel_btn = Button(text="Cancel", size_hint_y=None, height=40, background_normal='', background_color=(0.5, 0.5, 0.5, 1))
            content.add_widget(confirm_btn)
            content.add_widget(cancel_btn)

            confirm_popup = Popup(title="Confirm Delete", content=content, size_hint=(0.8, 0.4))
            confirm_btn.bind(on_release=lambda x: self.delete_bill(bill, popup, confirm_popup))
            cancel_btn.bind(on_release=lambda x: confirm_popup.dismiss())
            confirm_popup.open()
        except Exception as e:
            self.notify("Error", f"Failed to open delete confirmation: {str(e)}")
            log_crash(e, source="confirm_delete")

    def delete_bill(self, bill, popup, confirm_popup):
        try:
            self.bills.remove(bill)
            self.save_bills()
            self.update_view()
            self.schedule_notifications()
            popup.dismiss()
            confirm_popup.dismiss()
            self.notify("Bill Deleted", f"{bill['name']} has been deleted")
        except Exception as e:
            self.notify("Error", f"Failed to delete bill: {str(e)}")
            log_crash(e, source="delete_bill")

    def filter_bills(self, text):
        try:
            self.update_view()
        except Exception as e:
            self.notify("Error", f"Failed to filter bills: {str(e)}")
            log_crash(e, source="filter_bills")

    def get_export_dir(self):
        try:
            if platform == 'android':
                try:
                    from jnius import autoclass
                    Environment = autoclass('android.os.Environment')
                    return os.path.join(Environment.getExternalStoragePublicDirectory(
                        Environment.DIRECTORY_DOCUMENTS).getPath(), 'BillsManager_Exports')
                except Exception:
                    return os.path.join(os.path.expanduser('~'), 'BillsManager_Exports')
            else:
                return os.path.join(os.path.expanduser('~'), 'Documents', 'BillsManager_Exports')
        except Exception as e:
            self.notify("Error", f"Failed to get export directory: {str(e)}")
            log_crash(e, source="get_export_dir")
            return os.path.join(os.path.expanduser('~'), 'Documents', 'BillsManager_Exports')

    def export_bills(self):
        try:
            if platform == 'android':
                try:
                    from android.permissions import request_permissions, Permission, check_permission
                    if not check_permission(Permission.WRITE_EXTERNAL_STORAGE):
                        request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
                except Exception as e:
                    self.notify("Permission Error", f"Failed to request permissions: {str(e)}")
                    log_crash(e, source="export_bills_permissions")
                    return
            export_dir = self.get_export_dir()
            os.makedirs(export_dir, exist_ok=True)
            export_path = os.path.join(export_dir, "bills_export.csv")
            with open(export_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Name", "Amount", "Paid", "Due", "Category", "Frequency"])
                for b in self.bills:
                    writer.writerow([b['name'], b['amount'], b['paid'], b['due'], b['category'], b.get('frequency', '')])
            self.notify("Bills Exported", f"Saved to {export_path}")
        except PermissionError:
            self.notify("Export Failed", "Permission denied. Please grant storage access.")
        except Exception as e:
            self.notify("Export Failed", f"Error: {str(e)}")
            log_crash(e, source="export_bills")

    def import_bills(self):
        try:
            if platform == 'android':
                try:
                    from android.permissions import request_permissions, Permission, check_permission
                    if not check_permission(Permission.READ_EXTERNAL_STORAGE):
                        request_permissions([Permission.WRITE_EXTERNAL_STORAGE, Permission.READ_EXTERNAL_STORAGE])
                except Exception as e:
                    self.notify("Permission Error", f"Failed to request permissions: {str(e)}")
                    log_crash(e, source="import_bills_permissions")
                    return
            import_dir = self.get_export_dir()
            import_paths = [
                os.path.join(import_dir, "bills_import.csv"),
                os.path.join(import_dir, "bills_import.txt")
            ]
            imported = False
            for import_path in import_paths:
                if not os.path.exists(import_path):
                    continue
                try:
                    with open(import_path, "r", newline="", encoding="utf-8") as f:
                        first_line = f.readline().strip()
                        f.seek(0)
                        required_fields = ["Name", "Amount", "Paid", "Due", "Category"]
                        is_csv = import_path.endswith(".csv")
                        if is_csv:
                            reader = csv.DictReader(f)
                            if not all(field in reader.fieldnames for field in required_fields):
                                self.notify("Import Warning", f"Invalid headers in {import_path}")
                                continue
                        else:
                            if not all(field in first_line.split(",") for field in required_fields):
                                self.notify("Import Warning", f"Invalid headers in {import_path}")
                                continue
                            next(f)
                            reader = [dict(zip(first_line.split(","), line.strip().split(","))) for line in f if line.strip()]
                        for row in reader:
                            if not all(field in row for field in required_fields):
                                self.notify("Import Warning", f"Skipped invalid bill: Missing fields in {row.get('Name', 'Unknown')}")
                                continue
                            if not re.match(r'^\d{2}/\d{2}/\d{4}$', row['Due']):
                                self.notify("Import Warning", f"Skipped invalid bill: Invalid date in {row.get('Name', 'Unknown')}")
                                continue
                            try:
                                amount = float(row['Amount'])
                                if amount <= 0:
                                    raise ValueError
                                datetime.datetime.strptime(row['Due'], '%d/%m/%Y')
                                self.bills.append({
                                    'name': row['Name'],
                                    'amount': amount,
                                    'paid': row['Paid'].lower() == 'true',
                                    'due': row['Due'],
                                    'category': row['Category'] if row['Category'] in BILL_CATEGORIES else 'Other',
                                    'frequency': row.get('Frequency', 'Custom')
                                })
                            except (ValueError, KeyError):
                                self.notify("Import Warning", f"Skipped invalid bill: {row.get('Name', 'Unknown')}")
                                continue
                        self.notify("Bills Imported", f"Imported from {import_path}")
                        imported = True
                except FileNotFoundError:
                    self.notify("Import Failed", f"No import file found at {import_path}")
                except Exception as e:
                    self.notify("Import Failed", f"Error reading {import_path}: {str(e)}")
                    log_crash(e, source="import_bills_read")
            if not imported:
                self.notify("Import Failed", f"No valid import files found in {import_dir}")
            if imported:
                self.save_bills()
                self.update_view()
                self.schedule_notifications()
        except Exception as e:
            self.notify("Error", f"Failed to import bills: {str(e)}")
            log_crash(e, source="import_bills")

    def backup_bills(self):
        try:
            export_dir = self.get_export_dir()
            os.makedirs(export_dir, exist_ok=True)
            backup_path = os.path.join(export_dir, f"bills_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            store.export(backup_path)
            self.notify("Backup Created", f"Saved to {backup_path}")
        except Exception as e:
            self.notify("Backup Failed", f"Error: {str(e)}")
            log_crash(e, source="backup_bills")

    def schedule_notifications(self):
        try:
            for callback in self.notification_callbacks:
                Clock.unschedule(callback)
            self.notification_callbacks = []
            today = datetime.datetime.now()
            for bill in self.bills:
                if bill['paid']:
                    continue
                try:
                    due_date = datetime.datetime.strptime(bill['due'], '%d/%m/%Y')
                    if due_date > today:
                        def callback(dt, b=bill):
                            self.notify("Bill Due Soon", f"{b['name']} due on {b['due']}")
                        delta = (due_date - today).total_seconds()
                        if delta > 0:
                            Clock.schedule_once(callback, max(delta - 86400, 0))
                            self.notification_callbacks.append(callback)
                except ValueError:
                    self.notify("Notification Error", f"Invalid date for {bill['name']}")
        except Exception as e:
            self.notify("Error", f"Failed to schedule notifications: {str(e)}")
            log_crash(e, source="schedule_notifications")

    def notify(self, title, message):
        try:
            notification.notify(title=title, message=message, timeout=5)
        except Exception as e:
            print(f"[ERROR] Notification failed: {str(e)}")
            self.show_toast(message)

    def show_toast(self, message):
        try:
            toast = Popup(
                title='',
                content=Label(text=message, color=(1, 1, 1, 1)),
                size_hint=(0.8, 0.2),
                pos_hint={'center_x': 0.5, 'top': 0.9},
                auto_dismiss=True
            )
            toast.open()
            Clock.schedule_once(lambda dt: toast.dismiss(), 2)
        except Exception as e:
            print(f"[ERROR] Toast failed: {str(e)}")
            log_crash(e, source="show_toast")

class SummaryScreen(Screen):
    def on_enter(self):
        try:
            today = datetime.datetime.now()
            total_paid = sum(float(b['amount']) for b in self.manager.get_screen('main').bills if b['paid'])
            total_remaining = sum(float(b['amount']) for b in self.manager.get_screen('main').bills if not b['paid'])
            overdue = sum(
                float(b['amount']) for b in self.manager.get_screen('main').bills
                if not b['paid'] and datetime.datetime.strptime(b['due'], '%d/%m/%Y') < today
            )

            currency_symbol = App.get_running_app().currency_symbol
            self.ids.total_paid.text = f"Total Paid: {currency_symbol}{total_paid:.2f}"
            self.ids.total_remaining.text = f"Total Remaining: {currency_symbol}{total_remaining:.2f}"
            self.ids.overdue.text = f"Overdue: {currency_symbol}{overdue:.2f}"

            container = self.ids.chart_container
            container.clear_widgets()
            try:
                from kivy_garden.graph import Graph, PiePlot
                graph = Graph(
                    xlabel='', ylabel='', x_ticks_minor=0, x_ticks_major=0,
                    y_ticks_major=0, y_grid_label=False, x_grid_label=False, padding=5
                )
                total = total_paid + total_remaining + overdue
                if total > 0:
                    plot = PiePlot()
                    plot.points = [
                        (total_paid, (0.3, 0.7, 0.3, 1)),
                        (total_remaining, (1, 0.4, 0.4, 1)),
                        (overdue, (1, 0.2, 0.2, 1))
                    ]
                    plot.labels = ['Paid', 'Remaining', 'Overdue']
                    graph.add_plot(plot)
                    container.add_widget(graph)
                else:
                    container.add_widget(Label(text="No data to display"))
            except ImportError:
                container.add_widget(Label(text="Pie chart unavailable (install kivy-garden.graph)"))
            except Exception as e:
                container.add_widget(Label(text=f"Chart error: {str(e)}"))
                log_crash(e, source="summary_chart")
        except Exception as e:
            self.notify("Error", f"Failed to load summary: {str(e)}")
            log_crash(e, source="summary_on_enter")

    def notify(self, title, message):
        try:
            notification.notify(title=title, message=message, timeout=5)
        except Exception as e:
            print(f"[ERROR] Notification failed: {str(e)}")
            self.show_toast(message)

    def show_toast(self, message):
        try:
            toast = Popup(
                title='',
                content=Label(text=message, color=(1, 1, 1, 1)),
                size_hint=(0.8, 0.2),
                pos_hint={'center_x': 0.5, 'top': 0.9},
                auto_dismiss=True
            )
            toast.open()
            Clock.schedule_once(lambda dt: toast.dismiss(), 2)
        except Exception as e:
            print(f"[ERROR] Toast failed: {str(e)}")
            log_crash(e, source="summary_show_toast")

class BillsManagerApp(App):
    theme = 'dark'
    currency_symbol = CURRENCY_SYMBOL

    def build(self):
        try:
            return Builder.load_string(KV)
        except Exception as e:
            log_crash(e, source="app_build")
            raise

    def switch_theme(self):
        try:
            self.theme = 'light' if self.theme == 'dark' else 'dark'
            for screen in self.root.screens:
                screen.canvas.before.clear()
                with screen.canvas.before:
                    Color(rgba=get_color_from_hex('#1A2E4B') if self.theme == 'dark' else get_color_from_hex('#E6F0FA'))
                    Rectangle(pos=screen.pos, size=screen.size)
                    Color(rgba=get_color_from_hex('#2E4A7D') if self.theme == 'dark' else get_color_from_hex('#A3CFFA'))
                    Rectangle(pos=(screen.x, screen.y + screen.height * 0.5), size=(screen.width, screen.height * 0.5))
                for widget in screen.walk(restrict=True):
                    if isinstance(widget, (Label, Button, TextInput)):
                        if isinstance(widget, Label) and hasattr(widget, 'id') and widget.id == 'remaining':
                            widget.color = get_color_from_hex('#FFD700') if self.theme == 'dark' else get_color_from_hex('#FF8C00')
                        elif isinstance(widget, Label) and widget.id in ['total_paid', 'total_remaining']:
                            widget.color = get_color_from_hex('#FFFFFF') if self.theme == 'dark' else get_color_from_hex('#000000')
                        elif isinstance(widget, Label) and hasattr(widget, 'id') and widget.id == 'overdue':
                            widget.color = get_color_from_hex('#FF6666') if self.theme == 'dark' else get_color_from_hex('#CC3333')
                        elif isinstance(widget, Button):
                            if widget.text == 'Unlock':
                                widget.background_color = get_color_from_hex('#339999') if self.theme == 'dark' else get_color_from_hex('#66CCCC')
                            elif widget.text == 'Change PIN':
                                widget.background_color = get_color_from_hex('#994433') if self.theme == 'dark' else get_color_from_hex('#CC8866')
                            elif widget.text == 'Toggle Theme':
                                widget.background_color = get_color_from_hex('#555555') if self.theme == 'dark' else get_color_from_hex('#AAAAAA')
                            elif widget.text == 'Test Crash':
                                widget.background_color = get_color_from_hex('#FF4444') if self.theme == 'dark' else get_color_from_hex('#FF6666')
                            elif widget.text == 'Clear':
                                widget.background_color = get_color_from_hex('#994433') if self.theme == 'dark' else get_color_from_hex('#CC8866')
                            elif widget.text in ['Sort: Name', 'Sort: Amount', 'Sort: Due']:
                                widget.background_color = get_color_from_hex('#339999') if self.theme == 'dark' else get_color_from_hex('#66CCCC')
                            elif widget.text == 'Add Bill':
                                widget.background_color = get_color_from_hex('#339999') if self.theme == 'dark' else get_color_from_hex('#66CCCC')
                            elif widget.text == 'Summary':
                                widget.background_color = get_color_from_hex('#994433') if self.theme == 'dark' else get_color_from_hex('#CC8866')
                            elif widget.text == 'Backup':
                                widget.background_color = get_color_from_hex('#669933') if self.theme == 'dark' else get_color_from_hex('#99CC66')
                            elif widget.text == 'Import':
                                widget.background_color = get_color_from_hex('#555555') if self.theme == 'dark' else get_color_from_hex('#AAAAAA')
                            elif widget.text == 'Back to Bills':
                                widget.background_color = get_color_from_hex('#339999') if self.theme == 'dark' else get_color_from_hex('#66CCCC')
                            widget.color = get_color_from_hex('#FFFFFF') if self.theme == 'dark' else get_color_from_hex('#000000')
                        elif isinstance(widget, TextInput):
                            widget.background_color = get_color_from_hex('#FFFFFF1A') if self.theme == 'dark' else get_color_from_hex('#0000001A')
                            widget.foreground_color = get_color_from_hex('#FFFFFF') if self.theme == 'dark' else get_color_from_hex('#000000')
                if screen.name == 'main':
                    screen.update_view()
        except Exception as e:
            log_crash(e, source="switch_theme")
            self.root.screens[0].notify("Error", f"Failed to switch theme: {str(e)}")

if __name__ == '__main__':
    try:
        BillsManagerApp().run()
    except Exception as e:
        log_crash(e, source="main")
        raise