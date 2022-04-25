from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import *
from PyQt5.QtCore import *

import os.path

from GCodeModel import Model, Layer, Feature, Command, Child
from io import TextIOWrapper
import numpy as np

import matplotlib
from matplotlib.axes import Axes
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection

RENDER_BG_COLOR: str = '0.208'
RENDER_TEXT_COLOR: str = '0.8'


class MplCanvas(FigureCanvasQTAgg):
    axes: Axes

    def __init__(self, parent=None, width=5, height=4, dpi=100) -> None:
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True, facecolor=RENDER_BG_COLOR)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class ReferenceTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    model_reference: Child
    children_populated: bool = False

    def __init__(self, parent, model_reference: Child) -> None:
        super().__init__(parent)
        self.model_reference = model_reference


class TopLevelTreeItem(ReferenceTreeWidgetItem):
    def __init__(self, parent, model_reference: Layer) -> None:
        super().__init__(parent, model_reference)


class MainWindow(QtWidgets.QMainWindow):
    model: Model = None
    open_file: str = None
    gcode_render: MplCanvas
    model_render_reference: LineCollection = None

    splitter: QtWidgets.QSplitter
    splitter_last_pos: int = 500

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

    open_top_level_item: TopLevelTreeItem
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

    def update_item(self, item: ReferenceTreeWidgetItem, render: bool = True) -> None:
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
        
        if render:
            self.render_layer()
    
    def on_item_expanded(self, item: ReferenceTreeWidgetItem) -> None:
        if not item.children_populated:
            # Remove the placeholder
            placeholder = item.child(0)
            item.removeChild(placeholder)

            if isinstance(item.model_reference, Layer):
                layer = item.model_reference
                for feature in layer.get_features():
                    self.add_tree_item(item, feature, feature.name)
            elif isinstance(item.model_reference, Feature):
                feature = item.model_reference
                for command in feature.get_commands():
                    self.add_tree_item(item, command, command.command)
            
            item.children_populated = True

        if not isinstance(item, TopLevelTreeItem):
            return
        
        if (item == self.open_top_level_item):
            return
        
        if self.open_top_level_item != None:
            self.open_top_level_item.setExpanded(False)
        
        self.open_top_level_item = item
        self.command_tree.scrollToItem(item, QtWidgets.QAbstractItemView.ScrollHint.PositionAtTop)

        if not isinstance(item.model_reference, Layer):
            return

        current_layer = self.layer_count - self.command_tree.invisibleRootItem().indexOfChild(item)
        self.slider_layer.setValue(current_layer)
        self.render_layer(current_layer)
    
    def on_item_collapsed(self, item: ReferenceTreeWidgetItem) -> None:
        if not isinstance(item, TopLevelTreeItem):
            return
        
        if self.open_top_level_item != None:
            self.open_top_level_item.setExpanded(False)
            self.open_top_level_item = None

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
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open", "","GCode Files (*.gcode);;All Files (*)", options=options)

        if not filename:
            return

        self.open_file = filename
        self.setWindowTitle("GCode Editor - " + os.path.basename(filename))
        
        with open(filename, "r") as file:
            self.parse_and_fill_model(file)
    
    def save_file(self):
        if self.open_file == None:
            return

        with open(self.open_file, "w") as file:
            self.model.export(file)
    
    def saveas_file_dialog(self):
        if self.open_file == None:
            return

        options = QtWidgets.QFileDialog.Options()
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save As", "","GCode Files (*.gcode);;All Files (*)", options=options)

        if not filename:
            return

        self.open_file = filename
        self.setWindowTitle("GCode Editor - " + os.path.basename(filename))
        
        with open(filename, "w") as file:
            self.model.export(file)

    def on_selection_change(self):
        self.selection_change_timer.start(100)

    def on_selection_timer_timeout(self):
        self.render_layer()
    
    def resizeEvent(self, e: QtGui.QResizeEvent):
        self.splitter.setGeometry(self.centralWidget().rect())
        self.splitter.moveSplitter(self.splitter_last_pos, 1)

    def on_splitter_moved(self, pos: int, index: int) -> None:
        self.splitter_last_pos = pos
    
    ### ================ P U B L I C   F U N C T I O N S ================ ###

    def add_tree_item(self, parent: QtWidgets.QTreeWidgetItem, model_item: Child, text: str) -> ReferenceTreeWidgetItem:
        item: ReferenceTreeWidgetItem
        if parent == self.command_tree.invisibleRootItem():
            item = TopLevelTreeItem(None, model_item)
        else: 
            item = ReferenceTreeWidgetItem(None, model_item)

        item.setFlags(QtCore.Qt.ItemIsSelectable|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsEnabled)
        item.setText(0, text)
        self.update_item(item, False)

        parent.addChild(item)

        if not isinstance(model_item, Command):
            QtWidgets.QTreeWidgetItem(item) # Add placeholder to show an expand button
        
        return item
    
    def set_layer_count(self, count: int) -> None:
        self.layer_count = count
        self.slider_layer.setMaximum(count - 1)
        self.slider_layer.setValue(0)
    
    def update_render_zoom(self, zoom) -> None:
        if not 0.0 < zoom < 1.0:
            return

        self.zoom = zoom
        self.gcode_render.axes.set_xlim([self.printer_size_x / 2.0 * self.zoom, self.printer_size_x - self.printer_size_x / 2.0 * self.zoom])
        self.gcode_render.axes.set_ylim([self.printer_size_y / 2.0 * self.zoom, self.printer_size_y - self.printer_size_y / 2.0 * self.zoom])
        self.gcode_render.draw()
    
    def parse_and_fill_model(self, gcode_file: TextIOWrapper) -> None:
        self.command_tree.clear()
        self.open_top_level_item = None

        self.model = Model.parse_gcode(gcode_file)

        self.add_tree_item(self.command_tree.invisibleRootItem(), self.model.feature_post_print, "Post-Print")
        for index, layer in reversed(list(enumerate(self.model.get_layers()))):
            self.add_tree_item(self.command_tree.invisibleRootItem(), layer, "Layer " + str(index))
        self.add_tree_item(self.command_tree.invisibleRootItem(), self.model.feature_pre_print, "Pre-Print")
        
        self.set_layer_count(self.model.layer_count())
        # Force update
        self.on_slider_value_changed(0)
    
    def render_layer(self, index: int = None) -> None:
        if self.model == None:
            return
        
        if index == None:
            if self.open_top_level_item == None:
                return
            
            index = self.layer_count - self.command_tree.invisibleRootItem().indexOfChild(self.open_top_level_item)
        
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
        self.gcode_render.axes.set_xlim([self.printer_size_x / 2.0 * self.zoom, self.printer_size_x - self.printer_size_x / 2.0 * self.zoom])
        self.gcode_render.axes.set_ylim([self.printer_size_y / 2.0 * self.zoom, self.printer_size_y - self.printer_size_y / 2.0 * self.zoom])
        self.gcode_render.axes.set_aspect('equal')
        self.gcode_render.axes.add_collection(lc)
        self.gcode_render.draw()

    def setup_ui(self) -> None:
        self.setWindowTitle("GCode Editor")
        self.setMinimumSize(840, 420)

        self.open_top_level_item = None

        for _, brush in self.COLORS.items():
            brush.setStyle(QtCore.Qt.SolidPattern)

        centralwidget = QtWidgets.QWidget(self)

        self.splitter = QtWidgets.QSplitter(centralwidget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)

        grid_layout_widget = QtWidgets.QWidget(self.splitter)
        grid_layout = QtWidgets.QGridLayout(grid_layout_widget)

        self.command_tree = QtWidgets.QTreeWidget(grid_layout_widget)
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Expanding)
        self.command_tree.setSizePolicy(size_policy)
        self.command_tree.setMinimumSize(QtCore.QSize(300, 0))
        self.command_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.command_tree.header().setVisible(False)

        grid_layout.addWidget(self.command_tree, 0, 0, 2, 1)

        horizontal_layout = QtWidgets.QHBoxLayout()

        spacerItem = QtWidgets.QSpacerItem(250, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        horizontal_layout.addItem(spacerItem)

        self.button_remove = QtWidgets.QPushButton(grid_layout_widget)
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

        self.button_insert = QtWidgets.QPushButton(grid_layout_widget)
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


        grid_layout_widget_2 = QtWidgets.QWidget(self.splitter)
        grid_layout2 = QtWidgets.QGridLayout(grid_layout_widget_2)

        vertical_layout_2 = QtWidgets.QVBoxLayout()

        self.button_zoom_in = QtWidgets.QPushButton(grid_layout_widget_2)
        self.button_zoom_in.setText("+")
        self.button_zoom_in.setMinimumSize(QtCore.QSize(30, 30))
        self.button_zoom_in.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_zoom_in)

        self.button_zoom_out = QtWidgets.QPushButton(grid_layout_widget_2)
        self.button_zoom_out.setText("-")
        self.button_zoom_out.setMinimumSize(QtCore.QSize(30, 30))
        self.button_zoom_out.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_zoom_out)

        self.button_up = QtWidgets.QPushButton(grid_layout_widget_2)
        self.button_up.setText("▲")
        self.button_up.setMinimumSize(QtCore.QSize(30, 30))
        self.button_up.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_up)

        self.slider_layer = QtWidgets.QSlider(QtCore.Qt.Vertical, grid_layout_widget_2)
        self.slider_layer.setTickPosition(QtWidgets.QSlider.TicksAbove)
        self.slider_layer.setMaximum(0)
        vertical_layout_2.addWidget(self.slider_layer)

        self.button_down = QtWidgets.QPushButton(grid_layout_widget_2)
        self.button_down.setText("▼")
        self.button_down.setMinimumSize(QtCore.QSize(30, 30))
        self.button_down.setMaximumSize(QtCore.QSize(30, 30))
        vertical_layout_2.addWidget(self.button_down)

        grid_layout2.addLayout(vertical_layout_2, 0, 0, 2, 1)

        self.gcode_render = MplCanvas(self, width=5, height=5, dpi=100)

        self.gcode_render.axes.set_facecolor(RENDER_BG_COLOR)
        self.gcode_render.axes.xaxis.label.set_color(RENDER_TEXT_COLOR)
        self.gcode_render.axes.yaxis.label.set_color(RENDER_TEXT_COLOR)
        self.gcode_render.axes.tick_params(axis='x', colors=RENDER_TEXT_COLOR)
        self.gcode_render.axes.tick_params(axis='y', colors=RENDER_TEXT_COLOR)
        self.gcode_render.axes.spines['bottom'].set_color(RENDER_TEXT_COLOR)
        self.gcode_render.axes.spines['top'].set_color(RENDER_TEXT_COLOR)
        self.gcode_render.axes.spines['left'].set_color(RENDER_TEXT_COLOR)
        self.gcode_render.axes.spines['right'].set_color(RENDER_TEXT_COLOR)

        self.gcode_render.axes.set_xlim([0, self.printer_size_x])
        self.gcode_render.axes.set_ylim([0, self.printer_size_y])
        self.gcode_render.axes.set_aspect('equal')
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.gcode_render.setSizePolicy(size_policy)
        self.gcode_render.setMinimumSize(QtCore.QSize(400, 400))
        grid_layout2.addWidget(self.gcode_render, 0, 1, 2, 1)

        self.setCentralWidget(centralwidget)

        menubar = QtWidgets.QMenuBar(self)
        menubar.setGeometry(QtCore.QRect(0, 0, 1445, 21))

        self.menu_file = QtWidgets.QMenu(menubar)
        self.menu_file.setTitle("File")
        self.setMenuBar(menubar)

        self.action_file_open = QtWidgets.QAction(self)
        self.action_file_open.setText("Open...")
        self.action_file_open.setShortcut("Ctrl+O")

        self.action_file_save = QtWidgets.QAction(self)
        self.action_file_save.setText("Save")
        self.action_file_save.setShortcut("Ctrl+S")

        self.action_file_saveas = QtWidgets.QAction(self)
        self.action_file_saveas.setText("Save As...")
        self.action_file_saveas.setShortcut("Ctrl+Shift+S")

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
        self.action_file_save.triggered.connect(self.save_file)
        self.action_file_saveas.triggered.connect(self.saveas_file_dialog)
        self.command_tree.itemSelectionChanged.connect(self.on_selection_change)
        self.selection_change_timer.timeout.connect(self.on_selection_timer_timeout)
        self.splitter.splitterMoved.connect(self.on_splitter_moved)

        self.show()

class DarkPalette(QPalette):
    def __init__(self) -> None:
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
