import os
import json
import pickle
from datetime import datetime
from kivy.animation import Animation
from kivy.graphics import Color, Line, Rectangle
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.widget import Widget
from kivy.lang import Builder
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.list import TwoLineAvatarListItem, ImageLeftWidget
from kivymd.uix.card import MDCard
from kivymd.uix.selectioncontrol import MDCheckbox
from kivy.clock import Clock
import firebase_admin
from firebase_admin import credentials, db

# ========== ИНИЦИАЛИЗАЦИЯ FIREBASE ==========
# Скачайте serviceAccountKey.json из настроек Firebase проекта
# Если файла нет, работаем в офлайн-режиме (локально)
FIREBASE_CRED_PATH = "serviceAccountKey.json"
firebase_initialized = False

if os.path.exists(FIREBASE_CRED_PATH):
    try:
        cred = credentials.Certificate(FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://console.firebase.google.com/project/specialized-magazine/database/specialized-magazine-default-rtdb/data/~2F'  
        })
        firebase_initialized = True
        print("Firebase подключен")
    except Exception as e:
        print(f"Ошибка Firebase: {e}")
else:
    print("Файл serviceAccountKey.json не найден, работаю локально")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def load_from_firebase():
    """Загрузка всех записей из Firebase"""
    if not firebase_initialized:
        return []
    try:
        ref = db.reference('/welding_records')
        data = ref.get()
        if data:
            return list(data.values())
        return []
    except:
        return []

def save_to_firebase(record_id, record_data):
    """Сохранение/обновление записи в Firebase"""
    if not firebase_initialized:
        return
    try:
        ref = db.reference(f'/welding_records/{record_id}')
        ref.set(record_data)
    except Exception as e:
        print(f"Ошибка сохранения в Firebase: {e}")

def delete_from_firebase(record_id):
    """Удаление записи из Firebase"""
    if not firebase_initialized:
        return
    try:
        ref = db.reference(f'/welding_records/{record_id}')
        ref.delete()
    except Exception as e:
        print(f"Ошибка удаления из Firebase: {e}")

# ========== КЛАССЫ ЭКРАНОВ ==========
class MainScreen(MDScreen):
    def on_kv_post(self, base_widget):
        self.animate_title()

    def animate_title(self):
        if hasattr(self.ids, 'title_label'):
            label = self.ids.title_label
            label.opacity = 0
            label.font_size = dp(20)
            anim = Animation(opacity=1, font_size=dp(42), duration=0.6, t='out_back')
            anim.start(label)

    def go_to_add_record(self):
        self.manager.current = 'add_record'

    def go_to_list_records(self):
        self.manager.current = 'records_list'

class AddRecordScreen(MDScreen):
    def on_enter(self):
        # Загружаем последние сохранённые значения из состояния приложения
        app = MDApp.get_running_app()
        self.ids.object_input.text = app.last_object
        self.ids.welder_input.text = app.last_welder

    def save_record(self):
        # Сбор данных
        object_name = self.ids.object_input.text.strip()
        welder_name = self.ids.welder_input.text.strip()
        current_val = self.ids.current_slider.value
        voltage_val = self.ids.voltage_slider.value
        weld_type = self.ids.weld_type_spinner.text
        visual_control = self.ids.visual_check.active
        ultrasound_control = self.ids.ultrasound_check.active

        if not object_name or not welder_name:
            MDDialog(title="Ошибка", text="Заполните объект и сварщика").open()
            return

        record = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S%f'),
            'object': object_name,
            'welder': welder_name,
            'current': current_val,
            'voltage': voltage_val,
            'weld_type': weld_type,
            'visual': visual_control,
            'ultrasound': ultrasound_control,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'completed': False  # статус выполнения
        }

        # Сохраняем локально в JSON
        if not os.path.exists('data'):
            os.makedirs('data')
        records = []
        if os.path.exists('data/records.json'):
            with open('data/records.json', 'r', encoding='utf-8') as f:
                records = json.load(f)
        records.append(record)
        with open('data/records.json', 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        # Сохраняем в Firebase
        save_to_firebase(record['id'], record)

        # Сохраняем последние значения в состояние приложения
        app = MDApp.get_running_app()
        app.last_object = object_name
        app.last_welder = welder_name
        app.save_state()

        # Показываем анимацию на кнопке
        btn = self.ids.save_btn
        anim = Animation(size_hint=(0.9, None), height=dp(50), duration=0.1) + Animation(size_hint=(1, None), height=dp(50), duration=0.1)
        anim.start(btn)

        MDDialog(title="Успех", text="Запись добавлена").open()
        self.manager.current = 'records_list'

        def bind_values(self):
         """Обновление надписей при движении слайдеров"""
        def update_current(instance, value):
            if hasattr(self.ids, 'current_value_label'):
                self.ids.current_value_label.text = f"{int(value)} А"
        
        def update_voltage(instance, value):
            if hasattr(self.ids, 'voltage_value_label'):
                self.ids.voltage_value_label.text = f"{int(value)} В"
        
        self.ids.current_slider.bind(value=update_current)
        self.ids.voltage_slider.bind(value=update_voltage)

class RecordsListScreen(MDScreen):
    def on_enter(self):
        self.load_records()

    def load_records(self):
        """Загрузка записей из Firebase или локально"""
        self.ids.records_list.clear_widgets()
        records = []

        # Сначала пробуем Firebase
        fb_records = load_from_firebase()
        if fb_records:
            records = fb_records
        elif os.path.exists('data/records.json'):
            with open('data/records.json', 'r', encoding='utf-8') as f:
                records = json.load(f)

        # Фильтрация по объекту или сварщику
        filter_text = self.ids.filter_field.text.strip().lower()
        if filter_text:
            records = [r for r in records if filter_text in r.get('object', '').lower() or filter_text in r.get('welder', '').lower()]

        # Добавляем записи в список
        for rec in records:
            # Определяем иконки контроля качества
            control_icons = []
            if rec.get('visual'): control_icons.append("👁")
            if rec.get('ultrasound'): control_icons.append("🔊")
            control_str = " ".join(control_icons) if control_icons else "❌"

            # ДЛЯ ДЕСКТОПА (широкий экран) - используем карточки с чекбоксами
            if self.is_desktop():
                from kivymd.uix.card import MDCard
                from kivymd.uix.label import MDLabel
                from kivymd.uix.button import MDIconButton
                from kivy.uix.boxlayout import BoxLayout
                
                # Создаём карточку для одной записи
                card = MDCard(
                    orientation='horizontal',
                    padding=dp(10),
                    spacing=dp(10),
                    size_hint_y=None,
                    height=dp(80),
                    ripple_behavior=True,
                    on_release=lambda x, r=rec: self.show_detail(r)
                )
                
                # ЧЕКБОКС (слева)
                cb = MDCheckbox(
                    size_hint=(None, None),
                    size=(dp(48), dp(48)),
                    active=rec.get('completed', False)
                )
                cb.bind(active=lambda inst, val, r=rec: self.toggle_complete(r, val))
                
                # ИНФОРМАЦИЯ (по центру)
                info_layout = BoxLayout(orientation='vertical', size_hint_x=0.7)
                info_layout.add_widget(MDLabel(
                    text=f"{rec.get('object', '')} — {rec.get('welder', '')}",
                    font_style='H6',
                    size_hint_y=None,
                    height=dp(30)
                ))
                info_layout.add_widget(MDLabel(
                    text=f"Ток: {rec.get('current',0)}А | Напр: {rec.get('voltage',0)}В | Тип: {rec.get('weld_type','')} | Контроль: {control_str}",
                    theme_text_color='Secondary',
                    size_hint_y=None,
                    height=dp(25)
                ))
                
                # КНОПКА УДАЛЕНИЯ (справа)
                del_btn = MDIconButton(
                    icon="trash-can",
                    theme_text_color="Custom",
                    text_color=(1, 0, 0, 1),
                    size_hint_x=0.15
                )
                del_btn.bind(on_release=lambda x, r=rec: self.delete_record(r))
                
                # Собираем карточку
                card.add_widget(cb)
                card.add_widget(info_layout)
                card.add_widget(del_btn)
                
                # Добавляем карточку в список
                self.ids.records_list.add_widget(card)
            
            else:
                # ДЛЯ МОБИЛКИ (узкий экран) - просто текст
                item = TwoLineAvatarListItem(
                    text=f"{rec.get('object', '')} — {rec.get('welder', '')}",
                    secondary_text=f"Ток: {rec.get('current',0)}А | Напр: {rec.get('voltage',0)}В | Тип: {rec.get('weld_type','')} | Контроль: {control_str}",
                    on_release=lambda x, r=rec: self.show_detail(r)
                )
                self.ids.records_list.add_widget(item)

        # Обновляем график и прогресс-бар
        self.update_progress_chart(records)

        # Пустое сообщение (если нет записей)
        if hasattr(self.ids, 'empty_label'):
            self.ids.empty_label.opacity = 0 if len(self.ids.records_list.children) > 0 else 1

    def is_desktop(self):
        return Window.width > 600

    def toggle_complete(self, record, value):
        record['completed'] = value
        save_to_firebase(record['id'], record)
        self.update_local_record(record)
        self.load_records()

    def delete_record(self, record):
        delete_from_firebase(record['id'])
        self.delete_local_record(record['id'])
        self.load_records()

    def update_local_record(self, updated_record):
        if os.path.exists('data/records.json'):
            with open('data/records.json', 'r', encoding='utf-8') as f:
                records = json.load(f)
            for i, r in enumerate(records):
                if r['id'] == updated_record['id']:
                    records[i] = updated_record
                    break
            with open('data/records.json', 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

    def delete_local_record(self, record_id):
        if os.path.exists('data/records.json'):
            with open('data/records.json', 'r', encoding='utf-8') as f:
                records = json.load(f)
            records = [r for r in records if r['id'] != record_id]
            with open('data/records.json', 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

    def update_progress_chart(self, records):
        if not records:
            if hasattr(self.ids, 'progress_bar'):
                self.ids.progress_bar.value = 0
            self.draw_chart(0)
            return
        total = len(records)
        completed = sum(1 for r in records if r.get('completed', False))
        percent = int((completed / total) * 100) if total > 0 else 0
        if hasattr(self.ids, 'progress_bar'):
            self.ids.progress_bar.value = percent
        self.draw_chart(percent)

    def draw_chart(self, percent):
        chart_widget = self.ids.chart_widget
        chart_widget.canvas.clear()
        with chart_widget.canvas:
            Color(0.9, 0.9, 0.9, 1)
            Rectangle(pos=chart_widget.pos, size=chart_widget.size)
            Color(0.2, 0.8, 0.2, 1)
            Rectangle(pos=chart_widget.pos, size=(chart_widget.width * percent / 100, chart_widget.height))
            Color(0, 0, 0, 1)
            Line(rectangle=(chart_widget.x, chart_widget.y, chart_widget.width, chart_widget.height), width=2)

    def show_detail(self, record):
        detail_text = f"""Объект: {record.get('object', '')}
Сварщик: {record.get('welder', '')}
Ток: {record.get('current', 0)} А
Напряжение: {record.get('voltage', 0)} В
Тип шва: {record.get('weld_type', '')}
Контроль визуальный: {'Да' if record.get('visual') else 'Нет'}
Контроль ультразвук: {'Да' if record.get('ultrasound') else 'Нет'}
Дата: {record.get('date', '')}
Выполнено: {'Да' if record.get('completed') else 'Нет'}"""
        MDDialog(title="Детали записи", text=detail_text).open()

    def apply_filter(self):
        self.load_records()

# ========== ОСНОВНОЙ КЛАСС ПРИЛОЖЕНИЯ ==========
class WeldingJournalApp(MDApp):
    def build(self):
        self.theme_cls.primary_palette = "DeepOrange"
        self.theme_cls.theme_style = "Light"

        # Загружаем сохранённое состояние
        self.load_state()

        # Устанавливаем размер окна для десктопа
        if self.is_desktop():
            Window.size = (1100, 700)
        else:
            Window.size = (400, 700)

        # Загружаем kv файл
        Builder.load_file('welding.kv')

        sm = MDScreenManager()
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(AddRecordScreen(name='add_record'))
        sm.add_widget(RecordsListScreen(name='records_list'))

        return sm

    def is_desktop(self):
        return Window.width > 600

    def load_state(self):
        try:
            with open('app_state.pkl', 'rb') as f:
                state = pickle.load(f)
                self.last_object = state.get('last_object', '')
                self.last_welder = state.get('last_welder', '')
        except:
            self.last_object = ''
            self.last_welder = ''

    def save_state(self):
        state = {'last_object': self.last_object, 'last_welder': self.last_welder}
        with open('app_state.pkl', 'wb') as f:
            pickle.dump(state, f)

    def on_stop(self):
        self.save_state()

if __name__ == '__main__':
    WeldingJournalApp().run()