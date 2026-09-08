'''Database screen: list, load, save and delete saved birth charts.

A thin Kivy screen over the UI-agnostic core.chart_store. Loading a chart
fills the Home-screen form (so the user can review/edit before generating);
saving persists the birth data currently handed in from the Home or Chart
screen.
'''
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from core.chart_store import delete_chart, load_saved_charts, save_chart


class DatabaseScreen(Screen):
    '''Saved-birth-chart database browser and saver.'''

    list_container = ObjectProperty(None)
    status_label = ObjectProperty(None)
    name_input = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._context_bd = None

    def on_kv_post(self, base_widget):
        self._refresh()

    # -- data hand-off ------------------------------------------------------
    def set_context_birth_data(self, bd=None):
        '''Remember the birth data to save (from the Home or Chart screen).'''
        self._context_bd = bd

    def refresh_list(self):
        '''Rebuild the list of saved charts (call after any change).'''
        self._render_list()

    # -- actions ------------------------------------------------------------
    def save_current_chart(self):
        if self._context_bd is None:
            self._status('No chart to save. Enter birth data first.')
            return
        override = (self.name_input.text.strip() if self.name_input else '') or None
        record = save_chart(self._context_bd, override_name=override)
        self._context_bd = record.birth_data
        self._status(f'Saved "{record.name}".')
        if self.name_input is not None:
            self.name_input.text = ''
        self._refresh()

    def load_examples(self):
        from ui.presets import seed_example_charts
        added = seed_example_charts()
        if added:
            self._status(f'Loaded {added} example charts.')
        else:
            self._status('Example charts already loaded.')
        self._refresh()

    def load_chart(self, chart):
        home = self.manager.get_screen('home')
        home.apply_birth_data(chart.birth_data)
        self.manager.current = 'home'
        self._status(f'Loaded "{chart.name}" into the Home form.')

    def delete_chart(self, chart):
        delete_chart(chart.id)
        self._status(f'Deleted "{chart.name}".')
        self._refresh()

    def go_home(self):
        self.manager.current = 'home'

    # -- rendering ----------------------------------------------------------
    def _refresh(self):
        self._render_list()

    def _render_list(self):
        if self.list_container is None:
            return
        self.list_container.clear_widgets()
        charts = load_saved_charts()
        if not charts:
            self.list_container.add_widget(self._empty_state())
            return
        for chart in charts:
            self.list_container.add_widget(self._row(chart))

    def _empty_state(self):
        btn = Button(text='Load example charts (Famous people)',
                     size_hint_y=None, height=44)
        btn.bind(on_release=lambda *_: self.load_examples())
        return btn

    def _row(self, chart):
        row = BoxLayout(size_hint_y=None, height=88, spacing=6)
        label = Label(text=f'{chart.name}\n{chart.summary()}',
                      halign='left', valign='top', size_hint_x=0.6)
        label.bind(size=lambda inst, size: setattr(
            inst, 'text_size', (inst.width, inst.height)))
        load_btn = self._mini('Load', lambda *_: self.load_chart(chart))
        del_btn = self._mini('Delete', lambda *_: self.delete_chart(chart))
        row.add_widget(label)
        row.add_widget(load_btn)
        row.add_widget(del_btn)
        return row

    @staticmethod
    def _mini(text, cb):
        btn = Button(text=text, size_hint_x=0.175)
        btn.bind(on_release=cb)
        return btn

    def _status(self, text):
        if self.status_label is not None:
            self.status_label.text = text
