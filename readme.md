# superslicer_toolchanger post processing script

## intro:
This is a post processing script designed for use with superslicer (ss) and klipper, in particular printers setup to use klipper-toolchanger. (for example my Voron 350 build)

At the time of creating this project ss, while supporting multiple extruder prints, is still a bit lacking in that area, particularly when it comes to tool heating logic. While it is possible to hand craft some fancy custom gcode sections to bridge this gap to an extent, the output is still clunky, and to even get that far requires a depth of knowledge that seems to drive a lot of folks to other slicers with more mature and full featured tool changer support. Now I have tried many other slicers for just that reason, however I was left feeling as though I was sacrificing print quality for easier toolchanger setup, and that was my main motivation in developing this script. 

## goals:
- add intelligent tool preheating logic to ss output g-code files
- eliminate any g-code that ss inserts related to tool changes that you cannot control via slicer configurations
- to be simple enough to use that the average user adding a toolchanger can easily incorporate it into their ss configs
- to work well with klipper-toolchanger, and for most users at least, to not require significant tearup of their existing printer config files or macros

## Assumptions, setting expectations, and pre-requisites:
- you already have ss setup just how you like it, or at least functionally and you have tested it (this isn't a how-to for ss toolchangers for someone coming from a different slicer)
- your install and configs for klipper-toolchanger use the following standard macro naming conventions:
    - PRINT_START for the start of your print
        - in addition to any other variables you may currently be passing to PRINT_START, it is assumed (for now, remapping support may be added later) that your PRINT_START accepts the following temperature parameters: 
            - TOOL_TEMP
            - BED_TEMP
    - PRINT_END for the end of your print
    - T[Tool number] for performing a tool change
- you have configured your toolchanger such that ALL homing, bed mesh, QGL, etc MUST be performed using T0, regardless of whether or not T0 is used in a given print
- you are okay with preheating the bed to `first_layer_bed_temperature` and T0 to 150C prior to any homing, QGL, bed mesh, etc routines performed in your PRINT_START macro, this script adds this behavior.

# Superslicer setup

First and foremost, this is not a comprehensive guide to setting up ss for multiple extruders, at least not for now, I am assuming that you managed to locate the docs for prusa slicer and have set up your configs for basic multi extruder usage. The following is a non-exhaustive list of settings that need to be accounted for strictly for the purpose of this script performing as designed:
-  print settings --> multiple extruders --> ooze prevention
    - this needs to be enabled and a value set, even if it is zero
-  print settings --> output options --> post-processing script
    - this is where you will reference the post processing script (not covered in these instructions, you have google, no?)
- Filament settings:
    - overall: you need to have a configuration for each of your toolheads and any instructions here need to be performed for every toolhead
    - filament settings --> multimaterial --> multimaterial toolchange temperature
        - I only mention this to say that it is irrelevant and will be ignored
    - filament settings --> custom g-code --> start g-code
        - the very first line in this section must be `{current_extruder}`
            - anything else you may have had in this section is fine, it just has to go after the first line
            - this is necessary for two reasons:
                - first, if there was nothing in this section previously, it would not be inserted into the g-code output by ss, and we want it to be inserted
                - second, since these g-code blocks are inserted for each tool throughout the print, this serves as the identifier of which tool it corresponds to
    - filament settings --> custom g-code --> end g-code
        - the very first line in this section must be `{current_extruder}`
            - anything else you may have had in this section is fine, it just has to go after the first line
            - this is necessary for two reasons:
                - first, if there was nothing in this section previously, it would not be inserted into the g-code output by ss, and we want it to be inserted
                - second, since these g-code blocks are inserted for each tool throughout the print, this serves as the identifier of which tool it corresponds to
- Printer settings (other than custom g-code):
    - printer settings --> general --> capabilities --> extruders
        - this must be set to the number of toolheads that you have on your printer
        - changing this value will result in the addition of or removal of settings pages on the left sidebar
    - printer settings --> Extruder N
        - these are added or removed based on the number selected under the general settings group
        - I don't have any further guidance for these settings other than setting the preview color, but that will not affect anything else here
- Printer settings --> custom g-code
    - start g-code:
        - IMPORTANT NOTE: this section is the trickiest to setup, please pay attention to all of these instructions
        - pre-requisite conditions/modifications to your PRINT_START macro:
            - NOTE: I will be adding a sample/template PRINT_START macro
            - if not present, ensure that your PRINT_START macro accepts TOOL_TEMP and BED_TEMP parameters for setting tool and bed temperatures
            - if present, edit your PRINT_START macro to remove any preheating logic that may exist there, the goal is to consolidate nearly all temperature setting logic within the gcode
                - The one exception to this is the setting of tool temperature to to TOOL_TEMP performed by your PRINT_START macro
            - if present, remove any logic from your PRINT_START macro that heats the tool and/or bed for homing, QGL, bed mesh, etc, this will be handled by and added by this script
        - it is assumed that your start g-code section currently contains only a call to `PRINT_START` followed by some variables that are required by your macro
        - you may be used to seeing instructions telling you that this needs to be written on a single line ex: `PRINT_START TOOL_TEMP=123 BED=456...` and so forth, and this largely remains true, however you should do the following:
            - remove TOOL_TEMP parameter:
                - the reason for this is that since ss currently lacks `is_extruder_used` or other placeholders/variables that can be used to intelligently set tool temperatures you may be forced to configure ss such that you have an unnecessary added step of heating T0 to its `first_layer_temperature`
                - this script handles this by identifying whether or not T0 is the first tool used, whether it is used in the first layer, whether it is used in the near future, and:
                    - if it is the first tool used:
                        - TOOL_TEMP and BED_TEMP will be appended to the call to PRINT_START as normally expected
                    - if it is not the first tool used:
                        - if it is used in the near future, including the first layer:
                            - TOOL_TEMP will be set to first_layer_temperature - ooze prevention temperature
                        - if it is used in the near future, but not the first layer:
                            - TOOL_TEMP will be set to other layer temperature - ooze prevention temperature
                        - if it is not used in the print:
                            - TOOL_TEMP will be set to zero
                            - NOTE: if you do not already have this, the portion of your PRINT_START macro that sets final tool temperature should be converted to if-else logic such that if the temperature is set to zero the command will be M104 (set and don't wait) instead of the typical M109 (set and wait), otherwise the resulting behavior will be that you have to wait for T0 to cool to zero, which likely will never happen, even in an open chamber
            - remove BED_TEMP parameter:
                - the reason for this is similar to the reason for removing TOOL_TEMP, ss just doesn't have a great way currently of intelligently setting this value
                - this script handles that by looking at all of the tools used in the first layer and setting BED_TEMP to the highest `first_layer_bed_temperature` of the tools used, there will be similar logic used for setting the bed temperature at the start of the second layer
    - end g-code:
        - this section does not require any modifications, however it is assumed that you use this section to call PRINT_END and that your PRINT_END macro will perform a routine to turn off tool/bed heaters
    - before layer change g-code:
        - the very first line in this section must be `{current_extruder}`
            - anything else you may have had in this section is fine, it just has to go after the first line
            - this is necessary because ss will only insert this into the output if there is something in this section, and we want it in the output for this script to find
    - after layer change g-code:
        - the very first line in this section must be `{current_extruder}`
            - anything else you may have had in this section is fine, it just has to go after the first line
            - this is necessary because ss will only insert this into the output if there is something in this section, and we want it in the output for this script to find
        - IMPORTANT NOTE: if you are relying on your slicer to call `VERIFY_TOOL_DETECTED` or `VERIFY_TOOL_DETECTED ASYNC=1` then please ensure that you keep that in this section
    - tool change g-code:
        - the first line in this section must be `{current_extruder}`
        - the second line in this section must be `{next_extruder}`
        - there must be nothing else in this section that is related to tool changes, other things are fine, just do not include code to trigger the tool change, that will be inserted by this script
    - between extrusion role change g-code:
        - the very first line in this section must be `{current_extruder}`
        - anything else you may have had in this section is fine, it just has to go after the first line
        - this is necessary because ss will only insert this into the output if there is something in this section, and we want it in the output for this script to find




=====================================================================================
=====================================================================================
=====================================================================================
=====================================================================================
=====================================================================================
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
