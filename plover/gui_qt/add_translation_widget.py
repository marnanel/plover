
from collections import namedtuple

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QWidget

from plover.misc import shorten_path
from plover.steno import normalize_steno
from plover.engine import StartingStrokeState
from plover.translation import escape_translation, unescape_translation

from plover.gui_qt.add_translation_widget_ui import Ui_AddTranslationWidget
from plover.gui_qt.i18n import get_gettext

_ = get_gettext()


class AddTranslationWidget(QWidget, Ui_AddTranslationWidget):

    ''' Add a new translation to the dictionary. '''

    EngineState = namedtuple('EngineState', 'dictionary_filter translator starting_stroke')

    def __init__(self, engine, dictionary_path=None):
        super(AddTranslationWidget, self).__init__()
        self.setupUi(self)
        self._engine = engine
        self._dictionaries = []
        self._reverse_order = False
        self._selected_dictionary = dictionary_path
        engine.signal_connect('config_changed', self.on_config_changed)
        self.on_config_changed(engine.config)
        engine.signal_connect('dictionaries_loaded', self.on_dictionaries_loaded)
        self.on_dictionaries_loaded(self._engine.dictionaries)

        self.strokes.installEventFilter(self)
        self.translation.installEventFilter(self)

        # Pre-populate the strokes or translations with last stroke/word.
        last_translation = None
        for t in reversed(engine.translator_state.translations):
            # Find the last undoable stroke.
            if t.has_undo():
                last_translation = t
                break
        if last_translation:
            # Grab the last-formatted word
            last_word = last_translation.formatting[-1].word
            if last_word:
                # If the last translation was created with the dictionary...
                if last_translation.english:
                    self.translation.setText(last_word.strip())
                    self.on_translation_edited()
                # Otherwise, it's just raw steno
                else:
                    self.strokes.setText(last_word.strip())
                    self.on_strokes_edited()
                    self.strokes.selectAll()

        with engine:
            self._original_state = self.EngineState(None,
                                                    engine.translator_state,
                                                    engine.starting_stroke_state)
            engine.clear_translator_state()
            self._strokes_state = self.EngineState(self._dictionary_filter,
                                                   engine.translator_state,
                                                   StartingStrokeState(True, False))
            engine.clear_translator_state()
            self._translations_state = self.EngineState(None,
                                                        engine.translator_state,
                                                        StartingStrokeState(True, False))
        self._engine_state = self._original_state
        self._focus = None

    def eventFilter(self, watched, event):
        if event.type() == QEvent.FocusIn:
            if watched == self.strokes:
                self._focus_strokes()
            elif watched == self.translation:
                self._focus_translation()
        elif event.type() == QEvent.FocusOut:
            if watched in (self.strokes, self.translation):
                self._unfocus()
        return False

    def _set_engine_state(self, state):
        with self._engine as engine:
            prev_state = self._engine_state
            if prev_state is not None and prev_state.dictionary_filter is not None:
                engine.remove_dictionary_filter(prev_state.dictionary_filter)
            engine.translator_state = state.translator
            engine.starting_stroke_state = state.starting_stroke
            if state.dictionary_filter is not None:
                engine.add_dictionary_filter(state.dictionary_filter)
            self._engine_state = state

    @staticmethod
    def _dictionary_filter(key, value):
        # Only allow translations with special entries. Do this by looking for
        # braces but take into account escaped braces and slashes.
        escaped = value.replace('\\\\', '').replace('\\{', '')
        special = '{#'  in escaped or '{PLOVER:' in escaped
        return not special

    def _unfocus(self):
        self._unfocus_strokes()
        self._unfocus_translation()

    def _focus_strokes(self):
        if self._focus == 'strokes':
            return
        self._unfocus_translation()
        self._set_engine_state(self._strokes_state)
        self._focus = 'strokes'

    def _unfocus_strokes(self):
        if self._focus != 'strokes':
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _focus_translation(self):
        if self._focus == 'translation':
            return
        self._unfocus_strokes()
        self._set_engine_state(self._translations_state)
        self._focus = 'translation'

    def _unfocus_translation(self):
        if self._focus != 'translation':
            return
        self._set_engine_state(self._original_state)
        self._focus = None

    def _strokes(self):
        strokes = self.strokes.text().replace('/', ' ').split()
        if not strokes:
            return ()
        return normalize_steno('/'.join(strokes))

    def _translation(self):
        translation = self.translation.text().strip()
        return unescape_translation(translation)

    def _update_items(self, dictionaries=None, reverse_order=None):
        if dictionaries is not None:
            self._dictionaries = dictionaries
        if reverse_order is not None:
            self._reverse_order = reverse_order
        iterable = self._dictionaries
        if self._reverse_order:
            iterable = reversed(iterable)
        self.dictionary.clear()
        for d in iterable:
            item = shorten_path(d.path)
            if not d.enabled:
                item += ' [' + _('disabled') + ']'
            self.dictionary.addItem(item)
        selected_index = 0
        if self._selected_dictionary is None:
            # No user selection, select first enabled dictionary.
            for n, d in enumerate(self._dictionaries):
                if d.enabled:
                    selected_index = n
                    break
        else:
            # Keep user selection.
            for n, d in enumerate(self._dictionaries):
                if d.path == self._selected_dictionary:
                    selected_index = n
                    break
        if self._reverse_order:
            selected_index = self.dictionary.count() - selected_index - 1
        self.dictionary.setCurrentIndex(selected_index)

    def on_dictionaries_loaded(self, dictionaries):
        # We only care about loaded writable dictionaries.
        dictionaries = [
            d
            for d in dictionaries.dicts
            if not d.readonly
        ]
        if dictionaries != self._dictionaries:
            self._update_items(dictionaries=dictionaries)

    def on_config_changed(self, config_update):
        if 'classic_dictionaries_display_order' in config_update:
            self._update_items(reverse_order=config_update['classic_dictionaries_display_order'])

    def on_dictionary_selected(self, index):
        if self._reverse_order:
            index = len(self._dictionaries) - index - 1
        self._selected_dictionary = self._dictionaries[index].path

    def on_strokes_edited(self):
        strokes = self._strokes()
        if strokes:
            translation = self._engine.raw_lookup(strokes)
            strokes = '/'.join(strokes)
            if translation is not None:
                fmt = _('{strokes} maps to "{translation}"')
                translation = escape_translation(translation)
            else:
                fmt = _('{strokes} is not in the dictionary')
            info = fmt.format(strokes=strokes, translation=translation)
        else:
            info = ''
        self.strokes_info.setText(info)

    def on_translation_edited(self):
        translation = self._translation()
        if translation:
            strokes = self._engine.reverse_lookup(translation)
            translation = escape_translation(translation)
            if strokes:
                fmt = _('"{translation}" is mapped from {strokes}')
                strokes = ', '.join('/'.join(x) for x in strokes)
            else:
                fmt = _('"{translation}" is not in the dictionary')
            info = fmt.format(strokes=strokes, translation=translation)
        else:
            info = ''
        self.translation_info.setText(info)

    def save_entry(self):
        self._unfocus()
        strokes = self._strokes()
        translation = self._translation()
        if strokes and translation:
            index = self.dictionary.currentIndex()
            if self._reverse_order:
                index = -index - 1
            dictionary = self._dictionaries[index]
            old_translation = self._engine.dictionaries[dictionary.path].get(strokes)
            self._engine.add_translation(strokes, translation,
                                         dictionary_path=dictionary.path)
            return dictionary, strokes, old_translation, translation

    def reject(self):
        self._unfocus()
        self._set_engine_state(self._original_state)
