Examples:
the complicated one from the prusa docs:
https://github.com/foreachthing/Slic3rPostProcessing/blob/a47d64c8b83459cf3bd2906a3e81172c07328f34/SPP-Python/Slic3rPostProcessor.py#L212

a simple one:
https://github.com/johnnyruz/PrusaScripts/blob/master/postprocess_mmutempchange.py


# how to notes

get first layer z/height:
- search for `; first_layer_height = [NUMBER]`

determine tools used in print:
- for index 0 to N
    - if search for T[index] gives result, tool is used in print

determine number of tools used
- follow determine tool used instructions
- use list of used tools to determine count which should give index bounds

get layer counts:
- search for `; total layers count = 15`

get last layer z:
- search for all occurrences of `;LAYER_CHANGE`
- use last list item `;Z:[number you want]`

For percentages and remaining times: 
- search for `M73 P[PCT] R[Time]`



# break down gcode into sections:
- special startup section (begins after comment blocks for image and basic extruder params, ends at first feature printing):
    - set time/percentage block
    - * custom start gcode
    - set units and relative distances block
    - * custom toolchange gcode [initial tool]
    - * custom start filament gcode [initial tool]
    - startup temperature setting block (*****)
    - * custom before layer change gcode
    - layer change block [first layer]
    - * custom after layer change gcode
    - initial pre-feature start block
- special first layer section (begins at first feature print custom gcode, ends at end first layer temperature block)
    - [initial tool]
        - for each feature:
            - * custom feature gcode extrusion role change
            - feature print block
        - * custom end filament gcode [initial tool]
        - set T[initial tool] temperature block for end of tool use
    - [in between tools]
        - * custom toolchange gcode [in between tools]
        - * custom start filament gcode [in between tools]
        - set T[in between tools] temperature block for start of tool use
        - initial pre-feature start block
        - for each feature:
            - * custom feature gcode extrusion role change
            - feature print block
        - * custom end filament gcode [in between tools]
        - set T[in between tools] temperature block for end of tool use
    - [last tool for layer]
        - * custom toolchange gcode [last tool for layer]
        - * custom start filament gcode [last tool for layer]
        - set T[last tool for layer] temperature block for start of tool use
        - initial pre-feature start
        - for each feature:
            - * custom feature gcode extrusion role change
            - feature print block
    - * custom before layer change gcode
    - layer change block
    - * custom after layer change gcode
    - first layer end set temperature block (*****)
- all other in between layers:
    - IF continuing with previous tool:
        - [first tool of layer]
            - initial pre-feature start
            - for each feature:
                - * custom feature gcode extrusion role change
                - feature print block
            - * custom end filament gcode [first tool of layer]
            - set T[first tool of layer] temperature block for end of tool use
    - ELSE:
        - [previous tool]
            - * custom end filament gcode [previous tool]
            - set T[previous tool] temperature block for end of tool use
        - [first tool of layer]
            - * custom toolchange gcode [first tool of layer]
            - * custom start filament gcode [first tool of layer]
            - initial pre-feature start
            - for each feature:
                - * custom feature gcode extrusion role change
                - feature print block
            - * custom end filament gcode [first tool of layer]
            - set T[first tool of layer] temperature block for end of tool use
    - [in between tools]
        - * custom toolchange gcode [in between tools]
        - * custom start filament gcode [in between tools]
        - set T[in between tools] temperature block for start of tool use
        - initial pre-feature start block
        - for each feature:
            - * custom feature gcode extrusion role change
            - feature print block
        - * custom end filament gcode [in between tools]
        - set T[in between tools] temperature block for end of tool use
    - [last tool for layer]
        - * custom toolchange gcode [last tool for layer]
        - * custom start filament gcode [last tool for layer]
        - set T[last tool for layer] temperature block for start of tool use
        - initial pre-feature start
        - for each feature:
            - * custom feature gcode extrusion role change
            - feature print block
    - * custom before layer change gcode
    - layer change block
    - * custom after layer change gcode
- (end of print)
    - * * * identify by searching for `;TYPE:Custom` which only occurs before print starts and after last layer
    - [for each tool used]
        - * custom end filament gcode [for each tool used]
    - * custom end print gcode
    - final percentage and time remaining update
- (basic print stats)
- (ss config)


# layer tool usage mapping, for each layer:
- list of tools used, in order of use
- for each tool use, percentage of layer used (maybe)

# tool usage mapping
- start by creating a list of tool usage in order



# heat logic
notes:
- can base off of M73 commands
- can base off of features
- can also do something along the lines of a naive count of move commands
    - or even just raw lines of gcode between tools (must purge blanks and comments for this to work)

startup temp logic
- bed:
    - bed temp should be set to the highest first layer bed temp of all tools used in FIRST LAYER ONLY

second+ layer temp logic
- bed:
    - bed temp should be set to the highest OTHER layer bed temp of all tools used in the entire print





# The following are available in all the custom gcode sections:

current_extruder = {current_extruder}
initial_extruder = {initial_extruder}
initial_tool = {initial_tool}

first_layer_print_max 0 = {first_layer_print_max[0]}
first_layer_print_min 0 = {first_layer_print_min[0]}
first_layer_print_size 0 = {first_layer_print_size[0]}

first_layer_print_max 1 = {first_layer_print_max[1]}
first_layer_print_min 1 = {first_layer_print_size[1]}
first_layer_print_size 1 = {first_layer_print_size[1]}

first_layer_print_max 2 = {first_layer_print_max[2]}
first_layer_print_min 2 = {first_layer_print_min[2]}
first_layer_print_size 2 = {first_layer_print_size[2]}

bed_temperature 0 = {bed_temperature[0]}
bed_temperature 1 = {bed_temperature[1]}
bed_temperature 2 = {bed_temperature[2]}

chamber_temperature 0 = {chamber_temperature[0]}
chamber_temperature 1 = {chamber_temperature[1]}
chamber_temperature 2 = {chamber_temperature[2]}

filament_toolchange_temp 0 = {filament_toolchange_temp[0]}
filament_toolchange_temp 1 = {filament_toolchange_temp[1]}
filament_toolchange_temp 2 = {filament_toolchange_temp[2]}

first_layer_bed_temperature 0 = {first_layer_bed_temperature[0]}
first_layer_bed_temperature 1 = {first_layer_bed_temperature[1]}
first_layer_bed_temperature 2 = {first_layer_bed_temperature[2]}

first_layer_temperature 0 = {first_layer_temperature[0]}
first_layer_temperature 1 = {first_layer_temperature[1]}
first_layer_temperature 2 = {first_layer_temperature[2]}

temperature 0 = {temperature[0]}
temperature 1 = {temperature[1]}
temperature 2 = {temperature[2]}

tool_name 0 = {tool_name[0]}
tool_name 1 = {tool_name[1]}
tool_name 2 = {tool_name[2]}
