import matplotlib
import os
from GCodeParser import Feature, Layer, Model, GCodeParser
from UI import DarkPalette, MainWindow
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QStyleFactory
import sys

def get_E(dist_x, dist_y, layer_height, extruder_width):
     dist = (dist_x**2 + dist_y**2)**0.5
     volume_flow = layer_height * extruder_width
     area = 3.14159265359 * (1.75/2.0)**2
     return volume_flow / area * dist
    
def main():
    filename = "AI3M_3DBenchy.gcode"

    if not os.path.exists(filename):
        print("File does not exist")
        return

    model: Model

    with open(filename, "r") as file:
        parser = GCodeParser()
        model = parser.parse(file)
        print(model.get_layer_count())
    

    app = QtWidgets.QApplication(sys.argv)

    app.setStyle(QStyleFactory.create("Fusion"))
    app.setPalette(DarkPalette())

    ui = MainWindow()
    ui.setup_ui()

    for index, layer in enumerate(model.layers):
        layer_item = ui.add_tree_item(ui.command_tree, "Layer " + str(index))
        for feature in layer.features:
            feature_item = ui.add_tree_item(layer_item, feature.name)
            for command in feature.commands:
                ui.add_tree_item(feature_item, command)

    sys.exit(app.exec_())

main()
