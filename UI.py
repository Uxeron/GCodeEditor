from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from GCodeModel import Model, Layer, Feature, Command, Child
from io import TextIOWrapper
import numpy as np

import matplotlib
from matplotlib.axes import Axes
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection

class MplCanvas(FigureCanvasQTAgg):
    axes: Axes

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)

class ReferenceTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    model_reference: Child

    def __init__(self, parent, model_reference: Child) -> None:
        super().__init__(parent)
        self.model_reference = model_reference

class LayerTreeItem(ReferenceTreeWidgetItem):
    def __init__(self, parent, model_reference: Layer) -> None:
        super().__init__(parent, model_reference)

class MainWindow():
    main_window: QtWidgets.QMainWindow

    model: Model = None
    gcode_render: MplCanvas
    model_render_reference: LineCollection = None

    command_tree: QtWidgets.QTreeWidget

    slider_layer: QtWidgets.QSlider
    slider_start: QtWidgets.QSlider
    slider_end: QtWidgets.QSlider

    button_zoom_in: QtWidgets.QPushButton
    button_zoom_out: QtWidgets.QPushButton
    button_insert: QtWidgets.QPushButton
    button_remove: QtWidgets.QPushButton
    button_up: QtWidgets.QPushButton
    button_down: QtWidgets.QPushButton

    menu_file: QtWidgets.QMenu
    action_file_open: QtWidgets.QAction
    action_file_save: QtWidgets.QAction
    action_file_saveas: QtWidgets.QAction

    open_layer_item: LayerTreeItem
    layer_count: int

    printer_size_x: int = 210
    printer_size_y: int = 210
    zoom: float = 0.0

    selection_change_timer: QTimer

    COLORS = {
        "WHITE"  : QtGui.QBrush(QtGui.QColor("white")),
        "BLACK"  : QtGui.QBrush(QtGui.QColor("black")),
        "RED"    : QtGui.QBrush(QtGui.QColor(255, 100, 100)),
        "GREEN"  : QtGui.QBrush(QtGui.QColor("green")),
        "BLUE"   : QtGui.QBrush(QtGui.QColor(100, 100, 255)),
        "CYAN"   : QtGui.QBrush(QtGui.QColor("cyan")),
        "MAGENTA": QtGui.QBrush(QtGui.QColor("magenta")),
        "YELLOW" : QtGui.QBrush(QtGui.QColor("yellow")),
        "GRAY"   : QtGui.QBrush(QtGui.QColor("gray")),
        }
    
    ### ================ S I G N A L   F U N C T I O N S ================ ###
    
    def remove_selected_items(self) -> None:
        selected_items: list[ReferenceTreeWidgetItem] = self.command_tree.selectedItems()
        root = self.command_tree.invisibleRootItem()

        for item in selected_items:
            item.model_reference.remove_from_parent()
            (item.parent() or root).removeChild(item)
        
        self.render_layer()

    
    def insert_new_item_under_selection(self) -> None:
        if len(self.command_tree.selectedItems()) == 0:
            return

        root = self.command_tree.invisibleRootItem()
        
        selected_item: ReferenceTreeWidgetItem = self.command_tree.selectedItems()[0]
        parent: ReferenceTreeWidgetItem = (selected_item.parent() or root)
        item_index = parent.indexOfChild(selected_item) + 1

        new_item: ReferenceTreeWidgetItem

        if isinstance(parent.model_reference, Feature):
            command = parent.model_reference.insert_command("", item_index)
            new_item = ReferenceTreeWidgetItem(None, command)
        elif isinstance(parent.model_reference, Layer):
            feature = Feature(parent.model_reference, "")
            parent.model_reference.insert_feature(feature, item_index)
            new_item = ReferenceTreeWidgetItem(None, feature)
        elif isinstance(parent.model_reference, Model):
            layer = Layer(parent.model_reference, "")
            parent.model_reference.insert_layer(layer, item_index)
            new_item = ReferenceTreeWidgetItem(None, layer)

        new_item.setFlags(QtCore.Qt.ItemIsSelectable|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsEnabled)
        parent.insertChild(item_index, new_item)
        self.command_tree.editItem(new_item)

    def update_item(self, item: ReferenceTreeWidgetItem) -> None:
        if self.model == None:
            return

        if isinstance(item.model_reference, Command):
            item.model_reference.parse_command(item.text(0))

        if item.text(0).startswith("G0"):
            item.setForeground(0, self.COLORS["MAGENTA"])
        elif item.text(0).startswith("G1"):
            item.setForeground(0, self.COLORS["BLUE"])
        elif item.text(0).startswith(";"):
            item.setForeground(0, self.COLORS["GREEN"])
        elif item.text(0).startswith("M"):
            item.setForeground(0, self.COLORS["RED"])
        else:
            item.setForeground(0, self.COLORS["WHITE"])
        
        self.render_layer()
    
    def on_item_expanded(self, item: ReferenceTreeWidgetItem) -> None:
        if not isinstance(item, LayerTreeItem):
            return
        
        if (item == self.open_layer_item):
            return
        
        if self.open_layer_item != None:
            self.open_layer_item.setExpanded(False)
        
        self.open_layer_item = item
        self.command_tree.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop)
        current_layer = self.layer_count - self.command_tree.invisibleRootItem().indexOfChild(item)
        self.slider_layer.setValue(current_layer)
        self.render_layer(current_layer)
    
    def on_item_collapsed(self, item: ReferenceTreeWidgetItem) -> None:
        if not isinstance(item, LayerTreeItem):
            return
        
        if self.open_layer_item != None:
            self.open_layer_item.setExpanded(False)
            self.open_layer_item = None

    def on_button_down_pressed(self):
        self.slider_layer.setValue(self.slider_layer.value() - 1)
    
    def on_button_up_pressed(self):
        self.slider_layer.setValue(self.slider_layer.value() + 1)
    
    def on_slider_value_changed(self, value):
        self.command_tree.invisibleRootItem().child(self.layer_count - value).setExpanded(True)
    
    def on_button_zoom_in_pressed(self):
        self.update_render_zoom(self.zoom + 0.1)
    
    def on_button_zoom_out_pressed(self):
        self.update_render_zoom(self.zoom - 0.1)
    
    def open_file_dialog(self):
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.main_window, "Select GCode", "","GCode Files (*.gcode);;All Files (*)", options=options)

        if not filename:
            return
        
        with open(filename, "r") as file:
            self.parse_and_fill_model(file)
    
    def on_selection_change(self):
        self.selection_change_timer.start(100)

    def on_selection_timer_timeout(self):
        self.render_layer()
    
    ### ================ P U B L I C   F U N C T I O N S ================ ###

    def add_tree_item(self, parent: QtWidgets.QWidget, modelItem: Child, text: str) -> ReferenceTreeWidgetItem:
        item: ReferenceTreeWidgetItem
        if parent == self.command_tree:
            item = LayerTreeItem(parent, modelItem)
        else:
            item = ReferenceTreeWidgetItem(parent, modelItem)

        item.setFlags(QtCore.Qt.ItemIsSelectable|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsEnabled)
        item.setText(0, text)
        
        return item
    
    def set_layer_count(self, count: int):
        self.layer_count = count
        self.slider_layer.setMaximum(count - 1)
        self.slider_layer.setValue(0)
    
    def update_render_zoom(self, zoom):
        if not 0.0 < zoom < 1.0:
            return

        self.zoom = zoom
        self.gcode_render.axes.set_xlim([self.printer_size_x / 2.0 * self.zoom, self.printer_size_x - self.printer_size_x / 2.0 * self.zoom])
        self.gcode_render.axes.set_ylim([self.printer_size_y / 2.0 * self.zoom, self.printer_size_y - self.printer_size_y / 2.0 * self.zoom])
        self.gcode_render.draw()
    
    def parse_and_fill_model(self, gcode_file: TextIOWrapper):
        self.command_tree.clear()
        self.open_layer_item = None

        self.model = Model.parse_gcode(gcode_file)

        post_print_layer_item = self.add_tree_item(self.command_tree, self.model.feature_post_print, "Post-Print")
        for command in self.model.feature_post_print.get_commands():
            self.add_tree_item(post_print_layer_item, command, command.command)

        for index, layer in reversed(list(enumerate(self.model.get_layers()))):
            layer_item = self.add_tree_item(self.command_tree, layer, "Layer " + str(index))
            for feature in layer.get_features():
                feature_item = self.add_tree_item(layer_item, feature, feature.name)
                for command in feature.get_commands():
                    self.add_tree_item(feature_item, command, command.command)

        pre_print_layer_item = self.add_tree_item(self.command_tree, self.model.feature_pre_print, "Pre-Print")
        for command in self.model.feature_pre_print.get_commands():
            self.add_tree_item(pre_print_layer_item, command, command.command)
        
        self.set_layer_count(self.model.layer_count())
        # Force update
        self.on_slider_value_changed(0)
    
    def render_layer(self, index: int = None):
        if self.model == None:
            return
        
        if index == None:
            if self.open_layer_item == None:
                return
            
            index = self.layer_count - self.command_tree.invisibleRootItem().indexOfChild(self.open_layer_item)
        
        layer = self.model.get_layer(index)

        selected_commands: dict[Command, int] = {}
        for item in self.command_tree.selectedItems():
            model_reference: Child = item.model_reference

            if isinstance(model_reference, Command):
                selected_commands[model_reference] = None
            elif isinstance(model_reference, Feature):
                selected_commands.update(dict.fromkeys(model_reference.get_commands(), None))

        x_coords = []
        y_coords = []
        colors = []

        if index == 0:
            x_coords.append(0.0)
            y_coords.append(0.0)
        else:
            found =  False
            for feature in reversed(self.model.get_layer(index - 1).get_features()):
                if found: break

                for command in reversed(feature.get_commands()):
                    if command.is_move_command:
                        x_coords.append(command.x)
                        y_coords.append(command.y)
                        found = True
                        break

        for feature in layer.get_features():
            for command in feature.get_commands():
                if command.is_move_command:
                    x_coords.append(command.x)
                    y_coords.append(command.y)
                    if command in selected_commands:
                        colors.append(command.selected_color)
                    else:
                        colors.append(command.color)

        x_coords_array = np.array(x_coords)
        y_coords_array = np.array(y_coords)
        colors_array = np.array(colors)

        points = np.array([x_coords_array, y_coords_array]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)

        lc = LineCollection(segments, colors=colors_array)

        self.gcode_render.axes.cla()
        self.gcode_render.axes.set_xlim([0, self.printer_size_x])
        self.gcode_render.axes.set_ylim([0, self.printer_size_y])
        self.gcode_render.axes.set_aspect('equal')
        self.gcode_render.axes.add_collection(lc)
        self.gcode_render.draw()
        self.update_render_zoom(self.zoom)

    def setup_ui(self):
        self.main_window = QtWidgets.QMainWindow()
        self.main_window.setWindowTitle("GCode Editor")
        self.main_window.resize(1445, 1022)

        self.open_layer_item = None

        for _, brush in self.COLORS.items():
            brush.setStyle(QtCore.Qt.SolidPattern)

        centralwidget = QtWidgets.QWidget(self.main_window)

        grid_layout = QtWidgets.QGridLayout(centralwidget)

        self.gcode_render = MplCanvas(self, width=5, height=5, dpi=100)
        self.gcode_render.axes.set_xlim([0, self.printer_size_x])
        self.gcode_render.axes.set_ylim([0, self.printer_size_y])
        self.gcode_render.axes.set_aspect('equal')
        grid_layout.addWidget(self.gcode_render, 0, 2, 1, 1)

        vertical_layout = QtWidgets.QVBoxLayout()
        vertical_layout.setSpacing(0)
        self.slider_end = QtWidgets.QSlider(QtCore.Qt.Horizontal, centralwidget)
        self.slider_end.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider_end.setMaximum(0)
        vertical_layout.addWidget(self.slider_end)

        self.slider_start = QtWidgets.QSlider(QtCore.Qt.Horizontal, centralwidget)
        self.slider_start.setInvertedAppearance(True)
        self.slider_start.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.slider_start.setMaximum(0)
        vertical_layout.addWidget(self.slider_start)

        grid_layout.addLayout(vertical_layout, 2, 2, 1, 1)

        self.command_tree = QtWidgets.QTreeWidget(centralwidget)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self.command_tree.setSizePolicy(size_policy)
        self.command_tree.setMinimumSize(QtCore.QSize(400, 0))
        self.command_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.command_tree.header().setVisible(False)

        grid_layout.addWidget(self.command_tree, 0, 0, 2, 1)

        horizontal_layout = QtWidgets.QHBoxLayout()

        spacerItem = QtWidgets.QSpacerItem(250, 20, QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Minimum)
        horizontal_layout.addItem(spacerItem)

        self.button_remove = QtWidgets.QPushButton(centralwidget)
        self.button_remove.setText("Remove")
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.button_remove.sizePolicy().hasHeightForWidth())
        self.button_remove.setSizePolicy(size_policy)
        self.button_remove.setMinimumSize(QtCore.QSize(50, 50))
        self.button_remove.setMaximumSize(QtCore.QSize(50, 50))
        self.button_remove.setBaseSize(QtCore.QSize(50, 50))
        horizontal_layout.addWidget(self.button_remove)

        self.button_insert = QtWidgets.QPushButton(centralwidget)
        self.button_insert.setText("Insert")
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.button_insert.sizePolicy().hasHeightForWidth())
        self.button_insert.setSizePolicy(size_policy)
        self.button_insert.setMinimumSize(QtCore.QSize(50, 50))
        self.button_insert.setMaximumSize(QtCore.QSize(50, 50))
        self.button_insert.setBaseSize(QtCore.QSize(50, 50))
        horizontal_layout.addWidget(self.button_insert)
        grid_layout.addLayout(horizontal_layout, 2, 0, 1, 1)
        vertical_layout_2 = QtWidgets.QVBoxLayout()

        self.button_zoom_in = QtWidgets.QPushButton(centralwidget)
        self.button_zoom_in.setText("+")
        self.button_zoom_in.setMinimumSize(QtCore.QSize(30, 30))
        self.button_zoom_in.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_zoom_in)

        self.button_zoom_out = QtWidgets.QPushButton(centralwidget)
        self.button_zoom_out.setText("-")
        self.button_zoom_out.setMinimumSize(QtCore.QSize(30, 30))
        self.button_zoom_out.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_zoom_out)

        self.button_up = QtWidgets.QPushButton(centralwidget)
        self.button_up.setText("▲")
        self.button_up.setMinimumSize(QtCore.QSize(30, 30))
        self.button_up.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_up)

        self.slider_layer = QtWidgets.QSlider(QtCore.Qt.Vertical, centralwidget)
        self.slider_layer.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider_layer.setMaximum(0)
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

        self.selection_change_timer = QTimer()
        self.selection_change_timer.setSingleShot(True)

        self.button_remove.pressed.connect(self.remove_selected_items)
        self.button_insert.pressed.connect(self.insert_new_item_under_selection)
        self.button_down.pressed.connect(self.on_button_down_pressed)
        self.button_up.pressed.connect(self.on_button_up_pressed)
        self.command_tree.itemChanged.connect(self.update_item)
        self.command_tree.itemExpanded.connect(self.on_item_expanded)
        self.command_tree.itemCollapsed.connect(self.on_item_collapsed)
        self.slider_layer.valueChanged.connect(self.on_slider_value_changed)
        self.button_zoom_in.pressed.connect(self.on_button_zoom_in_pressed)
        self.button_zoom_out.pressed.connect(self.on_button_zoom_out_pressed)
        self.action_file_open.triggered.connect(self.open_file_dialog)
        self.command_tree.itemSelectionChanged.connect(self.on_selection_change)
        self.selection_change_timer.timeout.connect(self.on_selection_timer_timeout)

        self.main_window.show()

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
    sys.exit(app.exec_())
