from io import TextIOWrapper
import matplotlib
import os

class Feature:
    name: str
    commands: list[str] = []


class Layer:
    index: int
    features: list[Feature] = []



def get_E(dist_x, dist_y, layer_thickness, extruder_width):
     dist = (dist_x**2 + dist_y**2)**0.5
     volume_flow = layer_thickness * extruder_width
     area = 3.14159265359 * (1.75/2.0)**2
     return volume_flow / area * dist




def main(gcode_file: TextIOWrapper) -> None:
    gcode = gcode_file.read()



    
def init():
    #filename = input("Enter gcode file name: ")
    filename = "AI3M_JSBox_E0.6_L0.4_Fuzzy.gcode"

    if not os.path.exists(filename):
        print("File does not exist")
        return

    with open(filename, "r") as file:
        main(file)

init()


#import sys
 #   from PyQt5.QtCore import QFile, QTextStream
  #  import breeze_resources

   # app = QtWidgets.QApplication(sys.argv)

    #file = QFile("dark.qss")
    #file.open(QFile.ReadOnly | QFile.Text)
    #stream = QTextStream(file)
    #app.setStyleSheet(stream.readAll())