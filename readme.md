## Intro:
This is a post processing script designed for use with superslicer (ss) and klipper, in particular printers setup to use klipper-toolchanger. (for example my Voron 350 build)

At the time of creating this project ss, while supporting multiple extruder prints, is still a bit lacking in that area, particularly when it comes to tool heating logic. While it is possible to hand craft some fancy custom gcode sections to bridge this gap to an extent, the output is still clunky, and to even get that far requires a depth of knowledge that seems to drive a lot of folks to other slicers with more mature and full featured tool changer support. Now I have tried many other slicers for just that reason, however I was left feeling as though I was sacrificing print quality for easier toolchanger setup, and that was my main motivation in developing this script. 

## Goals:
- add intelligent tool preheating logic to ss output g-code files
- eliminate any g-code that ss inserts related to tool changes that you cannot control via slicer configurations
- to be simple enough to use that the average user adding a toolchanger can easily incorporate it into their ss configs
- to work well with klipper-toolchanger, and for most users at least, to not require significant tearup of their existing printer config files or macros

## Assumptions, setting expectations, and pre-requisites:
- you already have ss setup just how you like it, or at least functionally and you have tested it (this isn't a how-to for ss toolchangers for someone coming from a different slicer)
- your install and configs for klipper-toolchanger use the following standard macro naming conventions:
    - `PRINT_START` for the start of your print (note: no variables should be passed to your `PRINT_START` for this script to work properly)
    - PRINT_END for the end of your print
    - T[Tool number] for performing a tool change
- you have configured your toolchanger such that ALL homing, bed mesh, QGL, etc MUST be performed using T0, regardless of whether or not T0 is used in a given print
- you are okay with preheating the bed to `first_layer_bed_temperature` and T0 to 150C prior to any homing, QGL, bed mesh, etc routines performed in your `PRINT_START` macro, this script adds this behavior.

# Superslicer setup

First and foremost, this is not a comprehensive guide to setting up ss for multiple extruders, at least not for now, but it is pretty close, and assuming that you managed to locate the docs for prusa slicer and have set up your configs for basic multi extruder usage this will get you the rest of the way. With that in mind, slicer configuration is only half of the battle, your printer must also be configured properly, I will at some point share my toolchanger configurations that pair with this ss configuration set. The following is a non-exhaustive list of settings that need to be accounted for strictly for the purpose of this script performing as designed:
-  print settings --> multiple extruders --> ooze prevention
    - this needs to be enabled and a value set, even if it is zero
-  print settings --> output options --> post-processing script
    - this is where you will reference the post processing script, it is simply the absolute filepath to where you store the script on your computer
- Filament settings:
    - overall: you need to have a configuration for each of your toolheads and any instructions here need to be performed for every toolhead
    - filament settings --> multimaterial --> multimaterial toolchange temperature
        - I only mention this to say that it is irrelevant and will be ignored
    - filament settings --> custom g-code --> start g-code
        - Putting anything in this section is optional and not required
        - If you choose to use this section, you can utilize it to set the following extruder-specific variables for the post process script to use:
            - NOTE: if you want to set any variables here, then you must set somewhere in this section:
                - `EXTRUDER={current_extruder}`
                - this is how the script identifies the extruder that the variables belong to
            - `WARMUP_TIME`
                - example: `WARMUP_TIME=90`
            - `WARMUP_FROM_OFF_TIME`
                - example: `WARMUP_FROM_OFF_TIME=110`
            - `DORMANT_TIME`
                - example: `DORMANT_TIME=120`
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
        - TLDR: this should just have the call to `PRINT_START`, all else is handled by this script
            - this script will ignore anything else in this section and replace it with `PRINT_START`
            - your `PRINT_START` macro should not set any temperatures
        - pre-requisite conditions/modifications to your `PRINT_START` macro:
            - if present, edit your `PRINT_START` macro to remove any preheating logic that may exist there, the goal is to consolidate nearly all temperature setting logic within the gcode
            - if present, remove any logic from your `PRINT_START` macro that heats the tool and/or bed for homing, QGL, bed mesh, etc, this will be handled by and added by this script
            - if present, remove any logic from your `PRINT_START` macro that selects the tool
        - you may be used to seeing instructions telling you that this needs to be written on a single line ex: `PRINT_START TOOL_TEMP=123 BED=456...` and so forth, and this largely remains true, however you should do the following:
            - remove `TOOL_TEMP` parameter:
                - the reason for this is that since ss currently lacks `is_extruder_used` or other placeholders/variables that can be used to intelligently set tool temperatures you may be forced to configure ss such that you have an unnecessary added step of heating T0 to its `first_layer_temperature`
                - this script handles this temperature control
            - remove `BED_TEMP` parameter:
                - the reason for this is similar to the reason for removing `TOOL_TEMP`, ss just doesn't have a great way currently of intelligently setting this value
                - this script handles that by looking at all of the tools used in the first layer and setting `BED_TEMP` to the highest `first_layer_bed_temperature` of the tools used, there will be similar logic used for setting the bed temperature at the start of the second layer
    - end g-code:
        - this section does not require any modifications, however it is assumed that you use this section to call `PRINT_END` and that your `PRINT_END` macro will perform a routine to turn off tool/bed heaters
    - after layer change g-code:
        - IMPORTANT NOTE: if you are relying on your slicer to call `VERIFY_TOOL_DETECTED` or `VERIFY_TOOL_DETECTED ASYNC=1` then please ensure that you keep that in this section
    - tool change g-code:
        - must include the following two lines:
            - `CURRENT_TOOL={current_extruder}`
            - `NEXT_TOOL={next_extruder}`
        - there must be nothing else in this section that is related to tool changes, other things are fine, just do not include code to trigger the tool change, that will be inserted by this script

# Final Notes:
- feel free to bug me with questions or requests, response times may vary!