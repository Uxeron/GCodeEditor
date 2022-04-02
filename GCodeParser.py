from io import TextIOWrapper


class Feature:
    name: str
    commands: list[str] = []


class Layer:
    features: list[Feature] = []


class Model:
    feature_pre_print: Feature = Feature()
    feature_post_print: Feature = Feature()
    layers: list[Layer] = []

    def get_layer_count(self) -> int:
        return len(self.layers)

    def __init__(self) -> None:
        self.feature_pre_print.name = "PRE_PRINT"
        self.feature_pre_print.name = "POST_PRINT"


class GCodeParser:
    FEATURE_TYPES = ("FILL", "SKIN", "SKIRT", "SUPPORT", "SUPPORT-INTERFACE", "WALL-INNER", "WALL-OUTER")

    parsed_model: Model
    layer_count: int

    state_pre_print: bool = True
    state_post_print: bool = False

    current_layer: Layer
    current_feature: Feature

    def set_layer_count(self, count: str) -> None:
        self.layer_count = int(count)

    def start_layer(self, _) -> None:
        if self.state_pre_print:
            self.state_pre_print = False
            self.current_feature = Feature()
            self.current_feature.name = "LAYER_START"

        self.current_layer = Layer()
    
    def end_layer(self, _) -> None:
        self.current_layer.features.append(self.current_feature)
        self.current_feature = Feature()
        self.parsed_model.layers.append(self.current_layer)
        self.current_layer = Layer()

        if self.parsed_model.get_layer_count() == self.layer_count:
            self.state_post_print = True
            self.current_feature = self.parsed_model.feature_post_print
    
    def start_feature(self, name: str) -> None:
        if self.current_feature != None:
            self.current_layer.features.append(self.current_feature)

        self.current_feature = Feature()
        self.current_feature.name = name
    
    def start_mesh(self, name: str) -> None:
        if name == "NONMESH":
            self.start_feature("LAYER_END")

    ANNOTATION_COMMANDS = {"LAYER_COUNT":set_layer_count, "LAYER":start_layer, "TIME_ELAPSED":end_layer, "TYPE":start_feature, "MESH":start_mesh}


    def parse_line(self, line: str) -> None:
        if not line.startswith(";"):
            self.current_feature.commands.append(line)
            return

        if len(line[1::].split(":")) != 2:
            return

        annotation_command, annotation_value = line[1::].split(":")
        annotation_value = annotation_value.strip()
        if annotation_command in self.ANNOTATION_COMMANDS:
            self.ANNOTATION_COMMANDS[annotation_command](self, annotation_value)


    def parse(self, gcode_file: TextIOWrapper) -> Model:
        self.parsed_model = Model()
        self.current_feature = self.parsed_model.feature_pre_print

        gcode_line = gcode_file.readline()

        while gcode_line != "":
            self.parse_line(gcode_line)
            gcode_line = gcode_file.readline()
        
        return self.parsed_model
