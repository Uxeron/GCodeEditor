from GCodeModel import Model, Command

import numpy as np

import matplotlib
from matplotlib.axes import Axes
from matplotlib.backend_bases import MouseButton
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection

from functools import partial

RENDER_BG_COLOR: str = '0.208'
RENDER_TEXT_COLOR: str = '0.8'

class _Viewport:
    _canvas_width: float = 210.0
    _canvas_height: float = 210.0
    _zoom_level: float = 0.0

    _center_x: float
    _center_y: float
    _width: float
    _height: float

    def __init__(self, width: float, height: float) -> None:
        self.set_canvas_size(width, height)

    def get_x(self) -> float:
        return self._center_x - (self._width / 2.0)
    
    def get_y(self) -> float:
        return self._center_y - (self._height / 2.0)
    
    def get_width(self) -> float:
        return self._center_x + (self._width / 2.0)
    
    def get_height(self) -> float:
        return self._center_y + (self._height / 2.0)

    def set_canvas_size(self, width: float, height: float) -> None:
        self._canvas_width = width
        self._canvas_height = height
        self._width = width
        self._height = height

        self._center_x = width / 2.0
        self._center_y = height / 2.0
    
    def set_zoom(self, zoom: float) -> None:
        if not 0.0 <= zoom < 1.0:
            return

        self._zoom_level = zoom
        self._width  = self._canvas_width - self._canvas_width * zoom
        self._height = self._canvas_height - self._canvas_height * zoom

        self._normalize_viewport_position()
    
    def change_zoom(self, zoom_delta: float) -> None:
        self.set_zoom(self._zoom_level + zoom_delta)

    def set_center(self, x: float, y: float) -> None:
        self._center_x = x
        self._center_y = y

        self._normalize_viewport_position()

    def move_center(self, delta_x: float, delta_y: float) -> None:
        self.set_center(self._center_x + delta_x, self._center_y + delta_y)
    
    def _normalize_viewport_position(self) -> None:
        if self._center_x - (self._width / 2.0) < 0.0:
            self._center_x = self._width / 2.0
        
        if self._center_y - (self._height / 2.0) < 0.0:
            self._center_y = self._height / 2.0
        
        if self._center_x + (self._width / 2.0) > self._canvas_width:
            self._center_x = self._canvas_width - (self._width / 2.0)
        
        if self._center_y + (self._height / 2.0) > self._canvas_height:
            self._center_y = self._canvas_height - (self._height / 2.0)


class MplCanvas(FigureCanvasQTAgg):
    axes: Axes
    canvas_size_x: int = 210
    canvas_size_y: int = 210

    is_panning: bool = False
    pan_position_x: int
    pan_position_y: int
    viewport: _Viewport

    def __init__(self, parent=None, width=5, height=4, dpi=100) -> None:
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=True, facecolor=RENDER_BG_COLOR)
        self.axes = fig.add_subplot(111)

        self.viewport = _Viewport(self.canvas_size_x, self.canvas_size_y)

        super(MplCanvas, self).__init__(fig)
        on_press_partial = partial(self.on_press)
        on_release_partial = partial(self.on_release)
        on_drag_partial = partial(self.on_drag)
        self.mpl_connect('button_press_event', on_press_partial)
        self.mpl_connect('button_release_event', on_release_partial)
        self.mpl_connect('motion_notify_event', on_drag_partial)

        self.axes.set_facecolor(RENDER_BG_COLOR)
        self.axes.xaxis.label.set_color(RENDER_TEXT_COLOR)
        self.axes.yaxis.label.set_color(RENDER_TEXT_COLOR)
        self.axes.tick_params(axis='x', colors=RENDER_TEXT_COLOR)
        self.axes.tick_params(axis='y', colors=RENDER_TEXT_COLOR)
        self.axes.spines['bottom'].set_color(RENDER_TEXT_COLOR)
        self.axes.spines['top'].set_color(RENDER_TEXT_COLOR)
        self.axes.spines['left'].set_color(RENDER_TEXT_COLOR)
        self.axes.spines['right'].set_color(RENDER_TEXT_COLOR)

        self.axes.set_aspect('equal')
        self.axes.set_xlim([0, self.canvas_size_x])
        self.axes.set_ylim([0, self.canvas_size_y])

    def update_view(self) -> None:
        self.axes.set_xlim([self.viewport.get_x(), self.viewport.get_width()])
        self.axes.set_ylim([self.viewport.get_y(), self.viewport.get_height()])
        self.draw()

    def set_zoom(self, zoom_delta: float) -> None:
        self.viewport.change_zoom(zoom_delta)
        self.update_view()
    
    def on_press(self, event):
        if not event.button == MouseButton.LEFT:
            return

        self.is_panning = True
        self.pan_position_x = event.xdata
        self.pan_position_y = event.ydata

    def on_release(self, event):
        if not event.button == MouseButton.LEFT:
            return
        
        self.is_panning = False
    
    def on_drag(self, event):
        if not event.button == MouseButton.LEFT:
            return
        
        if not self.is_panning:
            return
        
        # If dragged outside the plot
        if event.xdata == None or event.ydata == None:
            return

        delta_x = self.pan_position_x - event.xdata
        delta_y = self.pan_position_y - event.ydata

        self.viewport.move_center(delta_x, delta_y)
        self.update_view()

    
    def render_layer(self, model: Model, index: int, selected_commands: dict[Command, int]) -> None:
        x_coords = []
        y_coords = []
        colors = []

        if index == 0:
            x_coords.append(0.0)
            y_coords.append(0.0)
        else:
            # Find the starting position of the print head from the previous layer
            found =  False
            for feature in reversed(model.get_layer(index - 1).get_features()):
                if found: break

                for command in reversed(feature.get_commands()):
                    if command.is_move_command:
                        x_coords.append(command.x)
                        y_coords.append(command.y)
                        found = True
                        break

        for feature in model.get_layer(index).get_features():
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

        self.axes.cla()
        self.axes.set_aspect('equal')
        self.axes.add_collection(lc)
        self.update_view()
