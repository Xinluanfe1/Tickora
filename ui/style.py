"""UI 设计令牌：macOS 浅色风格的配色、字体与对话框样式。"""

COLORS = {
    "window": "#F5F5F7",
    "sidebar": "#EFEFF2",
    "sidebar_border": "#E3E3E8",
    "main": "#F7F7F9",
    "card": "#FFFFFF",
    "text": "#1D1D1F",
    "secondary": "#6E6E73",
    "tertiary": "#8E8E93",
    "border": "#E5E5EA",
    "accent": "#007AFF",
    "accent_hover": "#0A6FE3",
    "selection": "#E1E1E6",
    "hover": "#E9E9ED",
}

# 紧迫程度边框：保留红/黄/白/灰语义，改用柔和的 macOS 色值
DUE_BORDER_COLORS = {
    "red": "#E57373",
    "yellow": "#E6B450",
    "white": "#ECECEE",
    "gray": "#D1D1D6",
}

PRIORITY_PILL = {
    "高": ("#FFE8E6", "#C42B1C"),
    "中": ("#FFF3DD", "#9A5B00"),
    "低": ("#E8F0FE", "#0B57D0"),
}

DIALOG_QSS = """
QDialog { background: #FFFFFF; }
QLabel { color: #1D1D1F; font-size: 13px; }
QLineEdit, QPlainTextEdit, QComboBox, QDateTimeEdit, QSpinBox {
    background: #F5F5F7;
    border: 1px solid #E3E3E8;
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: #007AFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QDateTimeEdit:focus, QSpinBox:focus {
    border: 1px solid #007AFF;
    background: #FFFFFF;
}
QPushButton {
    background: #FFFFFF;
    border: 1px solid #D2D2D7;
    border-radius: 8px;
    padding: 6px 14px;
}
QPushButton:hover { background: #F2F2F7; }
QPushButton:default {
    background: #007AFF;
    border: 1px solid #007AFF;
    color: #FFFFFF;
}
QPushButton:default:hover { background: #0A6FE3; }
QCheckBox { spacing: 8px; color: #3A3A3C; }
QGroupBox {
    border: 1px solid #E5E5EA;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
    color: #6E6E73;
}
QListWidget {
    background: transparent;
    border: none;
    outline: none;
}
QListWidget::item { padding: 7px 10px; border-radius: 8px; }
QListWidget::item:selected { background: #E3E3E8; color: #1D1D1F; }
QListWidget::item:hover { background: #F0F0F3; }
QDialogButtonBox QPushButton { min-width: 84px; }
"""
