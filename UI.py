from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

class MainWindow():
    main_window: QtWidgets.QMainWindow

    image:  QtWidgets.QLabel
    command_tree: QtWidgets.QTreeWidget

    slider_layer: QtWidgets.QSlider
    slider_start: QtWidgets.QSlider
    slider_end: QtWidgets.QSlider

    button_insert: QtWidgets.QPushButton
    button_remove: QtWidgets.QPushButton
    button_up: QtWidgets.QPushButton
    button_down: QtWidgets.QPushButton

    menu_file: QtWidgets.QMenu
    action_file_open: QtWidgets.QAction
    action_file_save: QtWidgets.QAction
    action_file_saveas: QtWidgets.QAction

    def show(self):
        self.main_window.show()

    def setup_ui(self):
        self.main_window = QtWidgets.QMainWindow()
        self.main_window.setWindowTitle("GCode Editor")
        self.main_window.resize(1445, 1022)

        centralwidget = QtWidgets.QWidget(self.main_window)

        grid_layout = QtWidgets.QGridLayout(centralwidget)

        self.image = QtWidgets.QLabel(centralwidget)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.image.setSizePolicy(size_policy)
        self.image.setPixmap(QtGui.QPixmap("DefaultImage.png"))
        grid_layout.addWidget(self.image, 0, 2, 1, 1)

        vertical_layout = QtWidgets.QVBoxLayout()
        vertical_layout.setSpacing(0)
        self.slider_end = QtWidgets.QSlider(QtCore.Qt.Horizontal, centralwidget)
        self.slider_end.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider_end.setValue(100)
        vertical_layout.addWidget(self.slider_end)

        self.slider_start = QtWidgets.QSlider(QtCore.Qt.Horizontal, centralwidget)
        self.slider_start.setInvertedAppearance(True)
        self.slider_start.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.slider_start.setValue(100)
        vertical_layout.addWidget(self.slider_start)

        grid_layout.addLayout(vertical_layout, 2, 2, 1, 1)

        self.command_tree = QtWidgets.QTreeWidget(centralwidget)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self.command_tree.setSizePolicy(size_policy)
        self.command_tree.setMinimumSize(QtCore.QSize(400, 0))
        self.command_tree.setDragEnabled(True)
        self.command_tree.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.command_tree.setAlternatingRowColors(True)
        self.command_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.command_tree.header().setVisible(False)

        ### <---- Add test items, remove later
        item_0 = QtWidgets.QTreeWidgetItem(self.command_tree)
        item_1 = QtWidgets.QTreeWidgetItem(item_0)
        item_0.setText(0, "Layer 0")
        item_1.setText(0, "G1 F1200 X52.866 Y88.433 E0.1115")
        brush = QtGui.QBrush(QtGui.QColor(0, 170, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        item_1.setForeground(0, brush)
        ### ---->

        grid_layout.addWidget(self.command_tree, 0, 0, 2, 1)

        horizontal_layout = QtWidgets.QHBoxLayout()

        spacerItem = QtWidgets.QSpacerItem(250, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        horizontal_layout.addItem(spacerItem)

        self.button_remove = QtWidgets.QPushButton(centralwidget)
        self.button_remove.setText("-")
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.button_remove.sizePolicy().hasHeightForWidth())
        self.button_remove.setSizePolicy(size_policy)
        self.button_remove.setMinimumSize(QtCore.QSize(50, 22))
        self.button_remove.setMaximumSize(QtCore.QSize(50, 50))
        self.button_remove.setBaseSize(QtCore.QSize(50, 50))
        horizontal_layout.addWidget(self.button_remove)

        self.button_insert = QtWidgets.QPushButton(centralwidget)
        self.button_insert.setText("+")
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.button_insert.sizePolicy().hasHeightForWidth())
        self.button_insert.setSizePolicy(size_policy)
        self.button_insert.setMinimumSize(QtCore.QSize(50, 22))
        self.button_insert.setMaximumSize(QtCore.QSize(50, 50))
        self.button_insert.setBaseSize(QtCore.QSize(50, 50))
        horizontal_layout.addWidget(self.button_insert)
        grid_layout.addLayout(horizontal_layout, 2, 0, 1, 1)
        vertical_layout_2 = QtWidgets.QVBoxLayout()

        self.button_up = QtWidgets.QPushButton(centralwidget)
        self.button_up.setText("▲")
        self.button_up.setMinimumSize(QtCore.QSize(30, 30))
        self.button_up.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_up)

        self.slider_layer = QtWidgets.QSlider(QtCore.Qt.Vertical, centralwidget)
        self.slider_layer.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider_layer.setValue(100)
        vertical_layout_2.addWidget(self.slider_layer)

        self.button_down = QtWidgets.QPushButton(centralwidget)
        self.button_down.setText("▼")
        self.button_down.setMinimumSize(QtCore.QSize(30, 30))
        self.button_down.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_down)

        grid_layout.addLayout(vertical_layout_2, 0, 1, 1, 1)

        self.main_window.setCentralWidget(centralwidget)

        menubar = QtWidgets.QMenuBar(self.main_window)
        menubar.setGeometry(QtCore.QRect(0, 0, 1445, 21))

        self.menu_file = QtWidgets.QMenu(menubar)
        self.menu_file.setTitle("File")
        self.main_window.setMenuBar(menubar)

        self.action_file_open = QtWidgets.QAction(self.main_window)
        self.action_file_open.setText("Open...")

        self.action_file_save = QtWidgets.QAction(self.main_window)
        self.action_file_save.setText("Save")

        self.action_file_saveas = QtWidgets.QAction(self.main_window)
        self.action_file_saveas.setText("Save As...")

        self.menu_file.addAction(self.action_file_open)
        self.menu_file.addAction(self.action_file_save)
        self.menu_file.addAction(self.action_file_saveas)
        menubar.addAction(self.menu_file.menuAction())

        QtCore.QMetaObject.connectSlotsByName(self.main_window)

class DarkPalette(QPalette):
    def __init__(self):
        super().__init__()

        self.setColor(QPalette.Window, QColor(53,53,53))
        self.setColor(QPalette.WindowText, Qt.white)
        self.setColor(QPalette.Base, QColor(25,25,25))
        self.setColor(QPalette.AlternateBase, QColor(53,53,53))
        self.setColor(QPalette.ToolTipBase, Qt.white)
        self.setColor(QPalette.ToolTipText, Qt.white)
        self.setColor(QPalette.Text, Qt.white)
        self.setColor(QPalette.Button, QColor(53,53,53))
        self.setColor(QPalette.ButtonText, Qt.white)
        self.setColor(QPalette.BrightText, Qt.red)
        self.setColor(QPalette.Link, QColor(42, 130, 218))
        self.setColor(QPalette.Highlight, QColor(42, 130, 218))
        self.setColor(QPalette.HighlightedText, Qt.black)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QStyleFactory

    app = QtWidgets.QApplication(sys.argv)

    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(DarkPalette())

    ui = MainWindow()
    ui.setup_ui()
    ui.show()
    sys.exit(app.exec_())
