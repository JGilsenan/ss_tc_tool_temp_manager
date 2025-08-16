# Intro:
This is a post processing script designed for use with superslicer (ss) and klipper, in particular printers setup to use klipper-toolchanger. (for example my Voron 350 build)

At the time of creating this project ss, while supporting multiple extruder prints, is still a bit lacking in that area, particularly when it comes to tool heating logic. While it is possible to hand craft some fancy custom gcode sections to bridge this gap to an extent, the output is still clunky, and to even get that far requires a depth of knowledge that seems to drive a lot of folks to other slicers with more mature and full featured tool changer support. Now I have tried many other slicers for just that reason, however I was left feeling as though I was sacrificing print quality for easier toolchanger setup, and that was my main motivation in developing this script. 

## Goals:
- add intelligent tool preheating logic to ss output g-code files
- eliminate any g-code that ss inserts related to tool changes that you cannot control via slicer configurations
- to be simple enough to use that the average user adding a toolchanger can easily incorporate it into their ss configs
- to work well with klipper-toolchanger, and for most users at least, to not require significant tearup of their existing printer config files or macros

## Assumptions, setting expectations, and pre-requisites:
- it is important to note that if you are generating gcode that uses a single tool and:
    - it is `T0`: there will be no modifications to the output gcode
    - it is not `T0`: there will be modifications to the output gcode, forcing `T0` for `PRINT_START`
- likewise, even if `T0` is not used in a print, it will be selected and used for `PRINT_START`
- you already have ss setup just how you like it, or at least functionally and you have tested it (this isn't a how-to for ss toolchangers for someone coming from a different slicer)
- your install and configs for klipper-toolchanger use the following standard macro naming conventions:
    - `PRINT_START` for the start of your print (note: no variables should be passed to your `PRINT_START` for this script to work properly)
    - PRINT_END for the end of your print
    - T[Tool number] for performing a tool change
    - `CLEAN_NOZZLE` for a nozzle cleaning routine
- you have configured your toolchanger such that ALL homing, bed mesh, QGL, etc MUST be performed using `T0`, regardless of whether or not `T0` is used in a given print
- you are okay with preheating the bed to `first_layer_bed_temperature` and `T0` to 150C prior to any homing, QGL, bed mesh, etc routines performed in your `PRINT_START` macro, this script adds this behavior.

# Superslicer setup

First and foremost, this is not a comprehensive guide to setting up ss for multiple extruders, at least not for now, but it is pretty close, and assuming that you managed to locate the docs for prusa slicer and have set up your configs for basic multi extruder usage this will get you the rest of the way. With that in mind, slicer configuration is only half of the battle, your printer must also be configured properly, I will at some point share my toolchanger configurations that pair with this ss configuration set. The following is a non-exhaustive list of settings that need to be accounted for strictly for the purpose of this script performing as designed:
-  print settings --> multiple extruders --> ooze prevention
    - whether or not you want this to be enabled (knowing that it adds a part-height skirt), a temperature should be set for this, as it will be used in the preheating of tools
    - if you choose not to enable ooze prevention, temporarily enable it to set the temperature then disable it again, the value you enter will still be exported if you do this
-  print settings --> output options --> post-processing script
    - this is where you will reference the post processing script, it is simply the absolute filepath to where you store the script on your computer
- Filament settings:
    - overall: you need to have a configuration for each of your toolheads and any instructions here need to be performed for every toolhead
    - filament settings --> multimaterial --> multimaterial toolchange temperature
        - I only mention this to say that it is irrelevant and will be ignored, even though it sounds like something you will need
    - filament settings --> custom g-code --> start g-code
        - Putting anything in this section is optional and not required
        - If you choose to use this section, you can utilize it to set the following extruder-specific variables for the post process script to use:
            - IMPORTANT: if you want to set any variables here, then you must set somewhere in this section:
                - `EXTRUDER={current_extruder}`
                - this is how the script identifies the extruder that the variables belong to
            - `WARMUP_TIME`
                - this designates how much time this extruder should be given to warm up before it is needed, if it is starting at the idle temperature (tool temperature if used now - ooze prevention offset) and transitioning to the temp it will be used at
                - example: `WARMUP_TIME=30`
                - this defaults to `30` if not provided, though the actual time varies by hotend and will most likely be lower
            - `WARMUP_FROM_OFF_TIME`
                - this designates how much time this extruder should be given to warm up to use temperature if it is off currently
                - example: `WARMUP_FROM_OFF_TIME=110`
                - this defaults to `90` if not provided
            - `DORMANT_TIME`
                - this designates the amount of time (approximated by this script) that this extruder needs to be not in use in order for it to be turned off completely in between uses (note: if it is turned off due to inactivity, the `WARMUP_FROM_OFF_TIME` is used for preheating it prior to its next use instead of `WARMUP_TIME`)
                - example: `DORMANT_TIME=120`
                - this defaults to `120` if not provided
            - `CLEAN_ON_FIRST_USE`
                - if set to `True`, then a call to the `CLEAN_NOZZLE` macro will be issued before using the tool for the first time in a print
                - this defaults to `True`
                - note that if `CLEAN_ON_EVERY_TOOLCHANGE` is set to True then `CLEAN_ON_FIRST_USE` is overridden
                - WARNING: you are responsible for ensuring that your `CLEAN_NOZZLE` macro is safe to run at any point during a print if this setting is set to `True`, simple nozzle cleaning macros that do not take measures to stay out of the print area can lead to collisions if this is enabled.
            - `CLEAN_ON_EVERY_TOOLCHANGE`
                - if set to `True`, then a call to the `CLEAN_NOZZLE` macro will be issued before using the tool each time it is selected
                - not that setting this to `True` overrides `CLEAN_ON_FIRST_USE` to be set to `True` as well
                - this defaults to `False`
                - WARNING: you are responsible for ensuring that your `CLEAN_NOZZLE` macro is safe to run at any point during a print if this setting is set to `True`, simple nozzle cleaning macros that do not take measures to stay out of the print area can lead to collisions if this is enabled.
            - example of a complete section for a given extruder: 
                ```
                EXTRUDER={current_extruder}
                WARMUP_TIME=30
                WARMUP_FROM_OFF_TIME=110
                DORMANT_TIME=120
                CLEAN_ON_FIRST_USE=True
                CLEAN_ON_EVERY_TOOLCHANGE=True
                ```
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
        - pre-requisite conditions/modifications to your `PRINT_START` macro, if present, remove the following:
            - any tool preheating logic that may exist there, the goal is to consolidate all temperature setting logic within the gcode
            - any logic that heats the tool and/or bed for homing, QGL, bed mesh, etc, this will be handled by and added by this script
            - any logic that selects the tool
        - Which `PRINT_START` macro:
            - I will upload a `PRINT_START` macro template that pairs with this post-process script
            - NOTE: you will be responsible for modifying the provided `PRINT_START` macro to match your current printer setup, as it will be minimal
            - NOTE: please look at the 'pre-requisite conditions/modifications' section above first
    - end g-code:
        - this section does not require any modifications, however it is assumed that you use this section to call `PRINT_END` and that your `PRINT_END` macro will perform a routine to turn off tool/bed heaters and move the toolhead
    - tool change g-code:
        - must include the following two lines:
            - `CURRENT_TOOL={current_extruder}`
            - `NEXT_TOOL={next_extruder}`
        - there must be nothing else in this section that is related to tool changes, other things are fine, just do not include code to trigger the tool change, that will be inserted by this script

# Usage
There's nothing more to do, once ss has referenced the script it will automatically run it each time you generate gcode

# What it does
- NOTE: if your print does not have any toolchanges, it does nothing and leaves the gcode as-is, make sure that your ss config is still valid if it doesn't get processed by this script
- eliminates ss's temperature setting logic that cannot be controlled via settings:
    - the post toolchange/post start filament temperature setting logic that ss uses inserts a set temperature and wait command that can cause long waiting periods in between tool changes while awaiting tool temperature stabilization
        - this logic is removed from the gcode output
        - this logic is replaced by the preheat logic paired with a plain set temperature command for the tool
        - but won't this introduce error? I know what you're thinking, if you don't let the tool temp stabilize you could start printing at the wrong temps, but fear not, assuming you aren't drastically wrong in your preheat time selection (in which case you were already going to have issues) the error should be no more than a degree or two. Furthermore, statically preheating your tool before you begin pushing plastic was always going to introduce error at or exceeding this magnitude once plastic extrusion begins and the melting strips heat off of your toolhead.
    - the tool/bed temperature setting logic at the beginning of the print
        - if you examine the gcode output of ss setup for tool changers there is a block of temperature setting that is inserted in the "start" section of the gcode output, it is difficult to control how that block gets generated by ss settings alone, so this script removes it entirely
        - initial tool/bed temperature setting logic is reintroduced by this process script and is described below
        - note that the initial bed temperature is set to the highest first layer bed temperature of all tools used in the print
    - the tool/bed temperature setting logic at the transition from layer 1 to 2
        - at the beginning of the second layer ss will change the temperature of the tool and/or bed if they are configured to use a different temperature for first layer vs other layers, this is fine when you have just one tool, but becomes clunky when there is more than one tool used in a print, this logic is eliminated
        - it is replaced with temperature changes for the active tool to its other layer temperature and for the bed to the highest other layer temperature of all tools used in the print
        - all other tool temperature transitions from first layer temperatures to other layer temperatures are built into the preheat logic, which is to say that if the tool is being preheated for use in the first layer it will be preheated to its first layer temperature and then set to that temperature again upon its selection, otherwise it will be preheated/set to its other layer temperature
    - the standard ss pre-dropoff tool temperature drop logic
        - I believe this is only relevant if you have ooze prevention enabled, but ss will drop the temperature of the current tool right before dropoff, this is eliminated
        - this logic is replaced by more sophisticated logic that looks forward in the print to determine if a tool is used again and if so how long it will be before it is picked up again
- regenerates a "start" section composed of the following:
    - pre-start
        - selects `T0`
        - sets `T0` temperature to 150C and sets bed temperature, waits for both to be reached
        - calls `CLEAN_NOZZLE` for initial nozzle cleaning
    - start
        - adds a simplified start gcode section containing only a call to `PRINT_START`
    - if `T0` is the first tool used
        - adds heatup command
        - adds `CLEAN_NOZZLE` called upon reaching print temperature
    - if `T0` is not the first tool used
        - adds heatup and wait for the first tool
        - adds code for selecting the first tool
        - adds `CLEAN_NOZZLE` called upon selecting the first tool
        - creates preheat logic and adds a preheat section before `PRINT_START` is called
- performs temperature changes for second layer
    - sets bed temperature to the maximum other layer bed temperature of tools used in the print
    - sets the tool temperature of the currently selected tool to other layer temperature
- regenerates each toolchange gcode section as follows:
    - sets the temperature of the incoming tool to its print temperature (without wait, since tool is preheated)
    - selects the incoming tool
    - verifies tool detected
    - depending on configuration performs the `CLEAN_NOZZLE` macro
    - if the outgoing tool is not used again its temperature is set to 0
    - if the outgoing tool is not used for more than the configured `DORMANT_TIME` its temperature is set to 0
    - if the outgoing tool is used again in less than the configured `DORMANT_TIME` its temperature is set to its print temperature adjusted by the ooze prevention temperature
- generates and inserts preheat code
    - the logic behind this is:
        - first, all gcode lines in the print are assigned a score that roughly approximates their "time" using a naive approach that takes total print time, subtracts the time constants used by ss for print start and tool changes
        - next, the algorithm looks at each toolchange event, examines which tool is being selected, and based on the configurations provided determines the time ahead of the tool selection at which preheating should occur
        - the algorithm then walks back through the gcode to approximate where to place the preheat event with the following caveats:
            - if it reaches the start of the print the tool will be preheated at the start
            - if it reaches another section where the tool is selected it does not insert a preheat block
        - once an approximate location is found, the script inserts a preheating block that preheats the tool according to what its print temperature will be at the tool selection event that is being preheated for






# Final Notes:
- feel free to bug me with questions or requests, response times may vary!