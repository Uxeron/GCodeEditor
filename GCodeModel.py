from __future__ import annotations
from io import TextIOWrapper


class Child:
    parent: Parent

    def __init__(self, parent: Parent, **kwargs) -> None:
        self.parent = parent
        super().__init__(**kwargs)

    def remove_from_parent(self) -> None:
        self.parent.remove_child(self)


class Parent:
    children: list[Child]

    def __init__(self, **kwargs) -> None:
        self.children = []
        super().__init__(**kwargs)

    def remove_child(self, child: Child) -> None:
        self.children.remove(child)


class Command(Child):
    command: str
    is_move_command: bool
    x: float
    y: float
    color: str
    selected_color: str

    def __init__(self, parent: Feature, command: str) -> None:
        super().__init__(parent=parent)
        self.is_move_command = False
        self.x = None
        self.y = None

        self.parse_command(command)

    def parse_command(self, command: str) -> None:
        self.command = command
        command_parts = command.split(" ")

        match command_parts[0]:
            case "G0":
                self.color = "red"
                self.selected_color = "darkturquoise"
            case "G1":
                self.color = "royalblue"
                self.selected_color = "gold"
            case _:
                return # Not a move command, no need to continue parsing

        # Parts can go in any order, need to check all of them
        for part in command_parts:
            if part.startswith("X"):
                self.x = float(part[1::])
            elif part.startswith("Y"):
                self.y = float(part[1::])
        
        # Move command must have both X and Y parts
        self.is_move_command = (self.x != None and self.y != None)


class Feature(Child, Parent):
    name: str

    def __init__(self, parent: Layer, name: str) -> None:
        super().__init__(parent=parent)
        self.name = name
    
    def add_command(self, command: str) -> Command:
        child = Command(self, command)
        self.children.append(child)
        return child
    
    def insert_command(self, command: str, index: int) -> Command:
        child = Command(self, command)
        self.children.insert(index, child)
        return child
    
    def get_command(self, index: int) -> Command:
        return self.children[index]

    def get_commands(self) -> list[Command]:
        return self.children
    
    def command_count(self) -> int:
        return len(self.children)


class Layer(Child, Parent):
    features: list[Feature]

    def __init__(self, parent: Model):
        super().__init__(parent=parent)
    
    def add_feature(self, feature: Feature):
        self.children.append(feature)
    
    def insert_feature(self, feature: Feature, index: int):
        self.children.insert(index, feature)
    
    def get_feature(self, index: int) -> Feature:
        return self.children[index]
    
    def get_features(self) -> list[Feature]:
        return self.children
    
    def feature_count(self) -> int:
        return len(self.children)


class Model(Parent):
    feature_pre_print: Feature
    feature_post_print: Feature

    def __init__(self) -> None:
        super().__init__()
        self.feature_pre_print = Feature(self, "PRE_PRINT")
        self.feature_post_print = Feature(self, "POST_PRINT")

    def add_layer(self, layer: Layer) -> None:
        self.children.append(layer)
    
    def insert_layer(self, layer: Layer, index: int) -> None:
        self.children.insert(index, layer)
    
    def get_layer(self, index: int) -> Layer:
        return self.children[index]
    
    def get_layers(self) -> list[Layer]:
        return self.children

    def layer_count(self) -> int:
        return len(self.children)
    
    def export(self, output_file: TextIOWrapper) -> None:
        _GcodeExporter.export_model(output_file, self)
    
    def parse_gcode(gcode_file: TextIOWrapper) -> Model:
        parser = _GCodeParser()
        return parser.parse(gcode_file)


class _GCodeParser:
    FEATURE_TYPES = ("FILL", "SKIN", "SKIRT", "SUPPORT", "SUPPORT-INTERFACE", "WALL-INNER", "WALL-OUTER")

    parsed_model: Model
    layer_count: int

    state_pre_print: bool = True
    state_post_print: bool = False

    current_layer: Layer
    current_feature: Feature

    def set_layer_count(self, count: str, _) -> bool:
        self.layer_count = int(count)
        return True

    def start_layer(self, _, __) -> bool:
        self.current_layer = Layer(self.parsed_model)
        self.current_feature = Feature(self.current_layer, "LAYER_START")
        return True
    
    def end_layer(self, _, command) -> bool:
        self.current_layer.add_feature(self.current_feature)
        self.parsed_model.add_layer(self.current_layer)

        a = self.parsed_model.layer_count()
        if self.parsed_model.layer_count() != self.layer_count:
            return True
        
        self.current_feature.add_command(command)
        self.current_feature = self.parsed_model.feature_post_print
        return False

    def start_feature(self, name: str, _) -> bool:
        # If we are already working with a feature, end it
        if self.current_feature != None:
            self.current_layer.add_feature(self.current_feature)

        self.current_feature = Feature(self.current_layer, name)
        return True
    
    def start_mesh(self, name: str, _) -> bool:
        if name == "NONMESH":
            self.start_feature("LAYER_END", None)
        return True

    ANNOTATION_COMMANDS = {"LAYER_COUNT":set_layer_count, "LAYER":start_layer, "TIME_ELAPSED":end_layer, "TYPE":start_feature, "MESH":start_mesh}

    def parse_line(self, line: str) -> None:
        # Commands
        if not line.startswith(";"):
            self.current_feature.add_command(line)
            return

        # Comments
        if len(line[1::].split(":")) != 2:
            self.current_feature.add_command(line)
            return

        # Command comments
        annotation_command, annotation_value = line[1::].split(":")
        if annotation_command in self.ANNOTATION_COMMANDS:
            if self.ANNOTATION_COMMANDS[annotation_command](self, annotation_value, line):
                self.current_feature.add_command(line)
        else:
            self.current_feature.add_command(line)

    def parse(self, gcode_file: TextIOWrapper) -> Model:
        self.parsed_model = Model()
        self.current_feature = self.parsed_model.feature_pre_print

        gcode_line = gcode_file.readline()

        while gcode_line != "":
            gcode_line = gcode_line.strip()
            self.parse_line(gcode_line)
            gcode_line = gcode_file.readline()
        
        return self.parsed_model


class _GcodeExporter:
    def export_model(output_file: TextIOWrapper, model: Model) -> None:
        output_file.writelines(command.command + '\n' for command in model.feature_pre_print.get_commands())
        for layer in model.get_layers():
            for feature in layer.get_features():
                output_file.writelines(command.command + '\n' for command in feature.get_commands())
        output_file.writelines(command.command + '\n' for command in model.feature_post_print.get_commands())
