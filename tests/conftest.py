import os

# Qt must not need a display for tests. Set before any QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
