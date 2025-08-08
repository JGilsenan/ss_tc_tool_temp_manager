#!/usr/bin/python
import sys
from shutil import ReadError
from typing import Any


CFG_DEFAULT_TIME_BEFORE_PREHEAT_S: int = 30
CFG_DEFAULT_TIME_BEFORE_PREHEAT_FROM_OFF_S: int = 90
CFG_DEFAULT_OFF_TIME_TO_GO_DORMANT_S: int = 120

class GcodeSection:
    _lines: list[str]
    tool: int

    prev_section: Any
    next_section: Any

    pre_start_gcode: bool
    start_gcode: bool
    initial_temperature_block: bool
    gcode_block: bool
    toolchange_gcode: bool
    initial_toolchange: bool
    layer_change_comments: bool
    layer_change_gcode: bool
    second_layer_temperature_block: bool

    first_layer_temps_used: bool
    other_layer_temps_used: bool

    score: float

    # for toolchange sections
    outgoing_tool: int
    incoming_tool: int
    last_deselect: bool
    heat_from_off: bool

    def __init__(
        self,
        first_line: str,
        tool: int
    ) -> None:
        self._lines = [first_line]
        self.tool = tool
        self.pre_start_gcode = False
        self.start_gcode = False
        self.initial_temperature_block = False
        self.gcode_block = False
        self.toolchange_gcode = False
        self.initial_toolchange = False
        self.layer_change_comments = False
        self.layer_change_gcode = False
        self.second_layer_temperature_block = False
        self.score = 0.0
        self.prev_section = None
        self.next_section = None
        self.first_layer_temps_used = False
        self.other_layer_temps_used = False
        self.outgoing_tool = -1
        self.incoming_tool = -1
        self.last_deselect = False
        self.heat_from_off = False

    def add_line(self, line: str) -> None:
        self._lines.append(line)
    
    def resolve_lines(self) -> list[str]:
        return self._lines

    def replace_lines(self, lines: list[str]) -> None:
        self._lines = lines


class ToolConfig:

    tool_number: int

    bed_temperature: int
    first_layer_bed_temperature: int
    temperature: int
    first_layer_temperature: int
    chamber_temperature: int

    tool_used: bool
    warmup_time_s: int
    warmup_from_off_time_s: int
    dormant_time_s: int

    def __init__(self, index: int) -> None:
        self.tool_number = index
        self.bed_temperature = 0
        self.first_layer_bed_temperature = 0
        self.temperature = 0
        self.first_layer_temperature = 0
        self.chamber_temperature = 0
        self.tool_used = False
        self.warmup_time_s = 0
        self.dormant_time_s = 0
        self.warmup_from_off_time_s = 0


class ToolchangerPostprocessor:


    _input_file_path: str
    _raw_lines: list[str]
    _output_lines: list[str]

    # print stats
    _layer_count: int
    _print_time_s: int
    _time_start_gcode: int
    _time_toolchange: int
    _standby_temp_delta: int

    # relevant ss configs
    _tool_count_overall: int

    # tool configs
    _tool_configs: list[ToolConfig]

    # special sections
    _end_print_section: list[str]
    _print_stats_section: list[str]
    _ss_configs_section: list[str]
    _middle_section: list[str]

    # sections
    _track_current_tool: int

    # linked list of sections
    _first_section: GcodeSection

    # score tracker
    _score_tracker: float
    _has_first_toolchange: bool

    def __init__(self, input_file_path: str) -> None:
        """
        Initialize the ToolchangerPostprocessor class.

        :param input_file_path: path to the input gcode file
        """
        self._input_file_path = input_file_path
        self._output_lines = []
        self._raw_lines = self._read_input_file()        
        self._layer_count = 0
        self._print_time_s = 0
        self._time_start_gcode = 0
        self._time_toolchange = 0
        self._print_stats_section = []
        self._ss_configs_section = []
        self._middle_section = []
        self._first_section = None  # type: ignore
        self._score_tracker = 0.0
        self._has_first_toolchange = False

    def _read_input_file(self) -> list[str]:
        """
        Read the input gcode file.

        :return: list of lines from the input file
        """
        try:
            with open(self._input_file_path, "r", encoding='UTF-8') as readfile:
                return readfile.readlines()
        except ReadError as exc:
            print('FileReadError:' + str(exc))
            sys.exit(1)

    def process_gcode(self) -> None:
        """
        Process the gcode file.
        """
        # only process if there is a tool change in the gcode
        if not self._has_tool_change_in_gcode():
            print('No tool change in gcode, exiting now.')
            sys.exit(0)

        # eliminate unneeded blank lines
        self._eliminate_blank_lines()
        # dump comments and images at top of file into output list
        self._process_comments_and_images_at_start_of_file()
        # process block before print start
        self._process_block_before_print_start()
        # extract slicer configs section
        self._extract_slicer_configs_section()
        # parse slicer configs
        self._parse_slicer_configs()
        # extract print stats section
        self._extract_print_stats_section()
        # parse print stats
        self._parse_print_stats()
        # initial score
        self._score_tracker = float(self._print_time_s - self._time_start_gcode)
        # extract end print section
        self._extract_end_gcode_section()
        # find tools used in print
        self._find_tools_used_in_print()
        # eliminate ss pre toolchange tool temp drop
        self._eliminate_ss_pre_toolchange_tool_temp_drop()
        # eliminate ss post start filament tool temp set
        self._eliminate_ss_post_start_filament_tool_temp_set()
        # process start filament gcode blocks for tool parameters
        self._process_start_filament_gcode_blocks_for_tool_parameters()
        # extract basic start info
        self._extract_basic_start_info()
        # parse the raw lines into sections
        self._parse_raw_lines_into_sections()
        # process the start section
        self._process_start_section()
        # process the second layer changes
        self._process_second_layer_changes()
        # process the toolchange sections
        self._process_toolchange_sections()
        # score the gcode blocks
        self._score_gcode_blocks()
        # add the turn off tool logic
        self._add_turn_off_tool_logic()
        # add the deselect temperature logic
        self._add_deselect_temperature_logic()
        # add the preheat logic
        self._add_preheat_logic()
        # reduce the linked list to the middle section
        self._reduce_linked_list_to_middle_section()
        # reconstruct the gcode for output
        self._reconstruct_for_output()
        # write the output file
        self._write_output_file()

    def _has_tool_change_in_gcode(self) -> bool:
        """
        Checks if the gcode has a tool change.
        """
        for line in self._raw_lines:
            if line.startswith('; custom gcode: toolchange_gcode'):
                return True
        return False

    def _eliminate_blank_lines(self) -> None:
        """
        Eliminate blank lines from the raw lines list.
        """
        self._raw_lines = [line for line in self._raw_lines if line.strip()]

    def _process_comments_and_images_at_start_of_file(self) -> None:
        """
        Takes all lines up to the first `M73` and immediately dumps them to output list
        as these are comments and images that are not relevant to the script
        """
        while not self._raw_lines[0].startswith('M73'):
            self._output_lines.append(self._raw_lines.pop(0))

    def _process_block_before_print_start(self) -> None:
        """
        Takes everything up to the start of the print start custom gcode section and
        dumps it to the output list.
        """
        while not self._raw_lines[0].startswith('; custom gcode: start_gcode'):
            self._output_lines.append(self._raw_lines.pop(0))

    def _extract_slicer_configs_section(self) -> None:
        """
        Extracts the slicer configs from the end of the raw lines list.
        """
        # first find the line that starts with `; SuperSlicer_config = begin`
        idx_begin: int = 0
        for i, line in enumerate(self._raw_lines):
            if line.startswith('; SuperSlicer_config = begin'):
                idx_begin = i
                break
        # then find the line that starts with `; SuperSlicer_config = end`
        idx_end = len(self._raw_lines) -1
        # then extract the lines, including the two lines that contain the begin and end
        self._ss_configs_section = self._raw_lines[idx_begin:idx_end + 1]
        # then remove these lines from the raw lines list
        self._raw_lines = self._raw_lines[:idx_begin] + self._raw_lines[idx_end + 1:]

    def _parse_slicer_configs(self) -> None:
        """
        Parse the slicer configs section to extract relevant configs at the top level
        as well as on a per-tool basis.
        """
        # standby_temp_delta
        for line in self._ss_configs_section:
            if line.startswith('; standby_temperature_delta ='):
                self._standby_temp_delta = int(line.split('=')[1].strip())
                break
        # time_start_gcode
        for line in self._ss_configs_section:
            if line.startswith('; time_start_gcode ='):
                self._time_start_gcode = int(line.split('=')[1].strip())
                break
        # time_toolchange
        for line in self._ss_configs_section:
            if line.startswith('; time_toolchange ='):
                self._time_toolchange = int(line.split('=')[1].strip())
                break
        # find overall tool count using bed_temperature
        for line in self._ss_configs_section:
            if line.startswith('; bed_temperature ='):
                self._tool_count_overall = len(line.split(','))
                break
        # create empty tool configs list
        self._tool_configs = [ToolConfig(index=tool_number) for tool_number in range(self._tool_count_overall)]
        # parse individual tool_configs
        # parse bed temperature
        for line in self._ss_configs_section:
            if line.startswith('; bed_temperature ='):
                bed_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(bed_temperatures):
                    self._tool_configs[i].bed_temperature = int(temp)
                break
        # parse chamber temperature
        for line in self._ss_configs_section:
            if line.startswith('; chamber_temperature ='):
                chamber_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(chamber_temperatures):
                    self._tool_configs[i].chamber_temperature = int(temp)
                break
        # parse first_layer_bed_temperature
        for line in self._ss_configs_section:
            if line.startswith('; first_layer_bed_temperature ='):
                first_layer_bed_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(first_layer_bed_temperatures):
                    self._tool_configs[i].first_layer_bed_temperature = int(temp)
                break
        # parse first_layer_temperature
        for line in self._ss_configs_section:
            if line.startswith('; first_layer_temperature ='):
                first_layer_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(first_layer_temperatures):
                    self._tool_configs[i].first_layer_temperature = int(temp)
                break
        # parse temperature
        for line in self._ss_configs_section:
            if line.startswith('; temperature ='):
                temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(temperatures):
                    self._tool_configs[i].temperature = int(temp)
                break

    def _extract_print_stats_section(self) -> None:
        """
        Extracts the print stats from the raw lines list. When this is called this will
        consist of the block of comments at the end of _raw_lines
        """
        output: list[str] = []
        # iterate through the raw lines list starting from the end
        while self._raw_lines[-1].startswith('; ') or len(self._raw_lines[-1].strip()) == 0:
            output.append(self._raw_lines.pop(-1))
        # reverse the output list
        output.reverse()
        self._print_stats_section = output

    def _parse_print_stats(self) -> None:
        """
        Parse the print stats section.
        """
        # parse layer count
        for line in self._print_stats_section:
            if line.startswith('; layer count:'):
                self._layer_count = int(line.split(':')[1].strip())
                break
        # parse print time to get minutes and seconds then convert to seconds
        print_time_line: str = ''
        for line in self._print_stats_section:
            if 'estimated printing time' in line:
                print_time_line = line
                break
        # now get just the time string, everything after the = sign
        print_time_line = print_time_line.split('=')[1].strip()
        # parse minutes if present and seconds
        minutes: int = 0
        seconds: int = 0
        if 'm' in print_time_line:
            minutes = int(print_time_line.split('m')[0].strip())
            seconds = int(print_time_line.split('m')[1].strip().split('s')[0].strip())
        else:
            seconds = int(print_time_line.split('s')[0].strip())
        self._print_time_s = (minutes * 60) + seconds

    def _extract_end_gcode_section(self) -> None:
        """
        Extracts the end of print section from the bottom of the raw lines list since this
        is not going to be modified by the script.
        """
        # find the M107 line, there should be only one
        idx_m107: int = 0
        for i, line in enumerate(self._raw_lines):
            if line.startswith('M107'):
                idx_m107 = i
                break
        # extract the M107 line and anything after it
        self._end_print_section = self._raw_lines[idx_m107:]
        # remove the M107 line from the raw lines list and anything after it
        self._raw_lines = self._raw_lines[:idx_m107]
    
    def _find_tools_used_in_print(self) -> None:
        """
        Find the tools used in the print.
        """
        for tool in range(self._tool_count_overall):
            for line in self._raw_lines:
                tool_name = f'T{tool}'
                if tool_name in line:
                    self._tool_configs[tool].tool_used = True
                    break

    def _eliminate_ss_pre_toolchange_tool_temp_drop(self) -> None:
        """
        SS automatically adds a temperature drop to the current tool immediately before
        a tool change, this eliminates those temperature commands so that this script 
        can perform its own temperature management.
        """
        output_lines: list[str] = []
        for i, line in enumerate(self._raw_lines):
            if line.startswith('M104'):
                next_line_check = (i + 1 < len(self._raw_lines) and 
                                 self._raw_lines[i + 1].strip() == 
                                 '; custom gcode: toolchange_gcode')
                if next_line_check:
                    continue
            output_lines.append(line)
        self._raw_lines = output_lines
    
    def _eliminate_ss_post_start_filament_tool_temp_set(self) -> None:
        """
        SS automatically adds a temperature set and wait for the new tool post start filament.
        This eliminates those temperature commands so that this script can perform its own
        temperature management.
        """
        output_lines: list[str] = []
        for i, line in enumerate(self._raw_lines):
            if line.startswith('M109'):
                prev_line_check = (i - 1 >= 0 and 
                                 self._raw_lines[i - 1].startswith('; custom gcode end: start_filament_gcode'))
                if prev_line_check:
                    continue
            output_lines.append(line)
        self._raw_lines = output_lines

    def _process_start_filament_gcode_blocks_for_tool_parameters(self) -> None:
        """
        Process the start filament gcode blocks for tool parameters.
        """
        for i in range(len(self._raw_lines)):
            if self._raw_lines[i].startswith('; custom gcode: start_filament_gcode'):
                open_line: int = i
                while not self._raw_lines[i].startswith('; custom gcode end: start_filament_gcode'):
                    i += 1
                close_line: int = i
                # check if the block is empty
                if open_line == close_line - 1:
                    # delete this block
                    self._raw_lines.pop(open_line)
                    self._raw_lines.pop(open_line)
                    # if here, then we deleted lines and want to start this from the beginning
                    return self._process_start_filament_gcode_blocks_for_tool_parameters()
                # now process the lines between open and close
                delete_lines: list[int] = []
                extruder_number: int = -1
                warmup_time_s: int = -1
                dormant_time_s: int = -1
                warmup_from_off_time_s: int = -1
                for j in range(open_line, close_line):
                    if self._raw_lines[j].startswith('EXTRUDER='):
                        extruder_number = int(self._raw_lines[j].split('=')[1].strip())
                        delete_lines.append(j)
                    elif self._raw_lines[j].startswith('WARMUP_TIME='):
                        warmup_time_s = int(self._raw_lines[j].split('=')[1].strip())
                        delete_lines.append(j)
                    elif self._raw_lines[j].startswith('WARMUP_FROM_OFF_TIME='):
                        warmup_from_off_time_s = int(self._raw_lines[j].split('=')[1].strip())
                        delete_lines.append(j)
                    elif self._raw_lines[j].startswith('DORMANT_TIME='):
                        dormant_time_s = int(self._raw_lines[j].split('=')[1].strip())
                        delete_lines.append(j)
                if extruder_number == -1 and warmup_time_s == -1 and dormant_time_s == -1 and warmup_from_off_time_s == -1:
                    # no params in this block, so just move on
                    continue
                # now add the tool config
                if warmup_time_s >= 0:
                    self._tool_configs[extruder_number].warmup_time_s = warmup_time_s
                else:
                    self._tool_configs[extruder_number].warmup_time_s = CFG_DEFAULT_TIME_BEFORE_PREHEAT_S
                if warmup_from_off_time_s >= 0:
                    self._tool_configs[extruder_number].warmup_from_off_time_s = warmup_from_off_time_s
                else:
                    self._tool_configs[extruder_number].warmup_from_off_time_s = CFG_DEFAULT_TIME_BEFORE_PREHEAT_FROM_OFF_S
                if dormant_time_s >= 0:
                    self._tool_configs[extruder_number].dormant_time_s = dormant_time_s
                else:
                    self._tool_configs[extruder_number].dormant_time_s = CFG_DEFAULT_OFF_TIME_TO_GO_DORMANT_S
                # now sort the delete lines descending
                delete_lines.sort(reverse=True)
                # now delete the lines
                for line_idx in delete_lines:
                    self._raw_lines.pop(line_idx)
                # if here, then we deleted lines and want to start this from the beginning
                return self._process_start_filament_gcode_blocks_for_tool_parameters()

    def _extract_basic_start_info(self) -> None:
        """Extract the basic start info from the raw start section list."""
        # find the toolchange gcode block in the raw start lines and extract the tool number to get initial tool
        in_toolchange_gcode_block: bool = False
        for line in self._raw_lines:
            if line.startswith('; custom gcode: toolchange_gcode'):
                in_toolchange_gcode_block = True
                continue
            if in_toolchange_gcode_block:
                if line.startswith('NEXT_TOOL'):
                    self._track_current_tool = int(line.split('=')[1].strip())
                    break

    def _parse_raw_lines_into_sections(self) -> None:
        """
        Parse the raw lines into sections.
        """
        new_section: GcodeSection | None = None
        initial_toolchange_found: bool = False
        initial_temperature_block_found: bool = False
        while len(self._raw_lines) > 0:
            # grab the top line
            line: str = self._raw_lines.pop(0)
            if line.startswith('; custom gcode: start_gcode'):
                # start of start gcode section
                new_section = self._insert_new_section_at_end(line)
                # mark it as start gcode
                new_section.start_gcode = True
                # now add all the lines that start with G1
                while not self._raw_lines[0].startswith('; custom gcode end: start_gcode'):
                    new_section.add_line(self._raw_lines.pop(0))
                # add the closing block
                new_section.add_line(self._raw_lines.pop(0))
                continue
            if line.startswith('G1'):
                # start of standard gcode section
                new_section = self._insert_new_section_at_end(line)
                # mark it as gcode block
                new_section.gcode_block = True
                # now add all the lines that start with G1
                while len(self._raw_lines) > 0 and self._raw_lines[0].startswith('G1'):
                    new_section.add_line(self._raw_lines.pop(0))
                continue
            if line.startswith('; custom gcode: toolchange_gcode'):
                # start of custom toolchange gcode section
                new_section = self._insert_new_section_at_end(line)
                # mark it as toolchange gcode
                new_section.toolchange_gcode = True
                # mark it as initial toolchange
                if not initial_toolchange_found:
                    new_section.initial_toolchange = True
                    initial_toolchange_found = True
                # now add all the up to and including the end of the toolchange gcode block
                while not self._raw_lines[0].startswith('; custom gcode end: toolchange_gcode'):
                    new_section.add_line(self._raw_lines.pop(0))
                # add the closing block
                new_section.add_line(self._raw_lines.pop(0))
                # determine the next tool to update the tracker
                for line in new_section.resolve_lines():
                    if line.startswith('NEXT_TOOL'):
                        self._track_current_tool = int(line.split('=')[1].strip())
                        break
                continue
            if line.startswith(';LAYER_CHANGE'):
                # parse layer change comments
                # start of layer change section
                new_section = self._insert_new_section_at_end(line)
                # mark it as layer change comments
                new_section.layer_change_comments = True
                new_section.add_line(self._raw_lines.pop(0))
                # add the next line to the section
                new_section.add_line(self._raw_lines.pop(0))
                initial_layer_change_found = True
                continue
            if line.startswith('; custom gcode: layer_gcode'):
                # start of custom toolchange gcode section
                new_section = self._insert_new_section_at_end(line)
                # mark it as layer change gcode
                new_section.layer_change_gcode = True
                # now add all the up to and including the end of the layer change gcode block
                while not self._raw_lines[0].startswith('; custom gcode end: layer_gcode'):
                    new_section.add_line(self._raw_lines.pop(0))
                # add the closing block
                new_section.add_line(self._raw_lines.pop(0))
                continue
            if (line.startswith('M104') or line.startswith('M109') or line.startswith('M140') or line.startswith('M190')) and not initial_temperature_block_found:
                # start of second layer temperature block
                new_section = self._insert_new_section_at_end(line)
                # mark it as initial temperature block
                new_section.initial_temperature_block = True
                initial_temperature_block_found = True
                # now add all the up to and including the end of the second layer temperature block
                while self._raw_lines[0].startswith('M104') or \
                        self._raw_lines[0].startswith('M140') or \
                        self._raw_lines[0].startswith('M109') or \
                        self._raw_lines[0].startswith('M190'):
                    new_section.add_line(self._raw_lines.pop(0))
                continue
            if (line.startswith('M104') or line.startswith('M109') or line.startswith('M140') or line.startswith('M190')):
                # start of second layer temperature block
                new_section = self._insert_new_section_at_end(line)
                # mark it as second layer temperature block
                new_section.second_layer_temperature_block = True
                # now add all the up to and including the end of the second layer temperature block
                while self._raw_lines[0].startswith('M104') or \
                        self._raw_lines[0].startswith('M140') or \
                        self._raw_lines[0].startswith('M109') or \
                        self._raw_lines[0].startswith('M190'):
                    new_section.add_line(self._raw_lines.pop(0))
                continue
            # for all other lines, non-special comment lines or unscored gcode line
            self._insert_new_section_at_end(line)

    def _process_start_section(self) -> None:
        """
        Process the start section.
        """
        current_section: GcodeSection
        # first find the maximum first layer bed temp of all the tools used in the print
        max_first_layer_bed_temp: int = 0
        for tool_config in self._tool_configs:
            if not tool_config.tool_used:
                continue
            if tool_config.first_layer_bed_temperature > max_first_layer_bed_temp:
                max_first_layer_bed_temp = tool_config.first_layer_bed_temperature

        # ------------------------------------------------------------
        # pre start gcode
        # ------------------------------------------------------------
        # next, create a custom gcode section 
        new_section: list[str] = []
        # add line for marking the section
        new_section.append(f'; custom gcode: pre_start_gcode\n')
        # add line for selecting T0
        new_section.append(f'T0 ; select T0\n')
        # add line for setting bed temperature (without wait)
        new_section.append(f'M140 S{max_first_layer_bed_temp} ; set bed temperature\n')
        # add line for setting T0 temperature (with wait)
        new_section.append(f'M109 S150 T0 ; set T0 temperature and wait\n')
        # add line for setting bed temperature (with wait)
        new_section.append(f'M190 S{max_first_layer_bed_temp} ; set bed temperature and wait\n')
        # add line for marking the section
        new_section.append(f'; custom gcode end: pre_start_gcode\n')
        new_section.append('\n')
        # now create a section to contain this and insert it at the start of the linked list
        new_section_section = self._insert_new_section_at_start(new_section[0])
        # mark it as start gcode
        new_section_section.pre_start_gcode = True
        # set the lines
        new_section_section.replace_lines(new_section)

        # ------------------------------------------------------------
        # start gcode
        # ------------------------------------------------------------
        # now find the existing start gcode section
        current_section = self._first_section
        while not current_section.start_gcode:
            current_section = current_section.next_section
        # score the section
        current_section.score = self._time_start_gcode
        # get the first tool from the start gcode section
        first_tool = current_section.tool

        # ------------------------------------------------------------
        # start temperature block
        # ------------------------------------------------------------
        # first, find the existing start temperature block
        current_section = self._first_section
        while not current_section.initial_temperature_block:
            current_section = current_section.next_section
        # delete the section
        self._delete_section(current_section)

        # ------------------------------------------------------------
        # first tool change gcode
        # ------------------------------------------------------------
        # find the first toolchange_gcode section and remove it
        current_section = self._first_section
        while not current_section.toolchange_gcode:
            current_section = current_section.next_section
        # delete the section
        self._delete_section(current_section)

        # ------------------------------------------------------------
        # toolchange gcode or temperature block
        # ------------------------------------------------------------
        # first find the existing start gcode section
        current_section = self._first_section
        while not current_section.start_gcode:
            current_section = current_section.next_section
        new_section = []
        if first_tool == 0:
            print('T0 is the first tool')
            # T0 is the first tool, so we need to set the temperature
            # add line for marking the section
            new_section.append(f'; custom gcode: first_tool_temperature\n')
            # add line for setting T0 temperature (with wait)
            new_section.append(f'M109 S{self._tool_configs[0].first_layer_temperature} T0 ; set T0 temperature and wait\n')
            # add line for marking the section
            new_section.append(f'; custom gcode end: first_tool_temperature\n')
            new_section.append('\n')
            # now create a section to contain this and insert it at the start of the linked list
            new_section_section = self._insert_section_after_section(current_section, new_section[0])
            new_section_section.toolchange_gcode = False
            new_section_section.tool = 0
            # next, replace the lines in the new section
            new_section_section.replace_lines(new_section)
        else:
            # determine if T0 is used in the print
            t0_used: bool = self._tool_configs[0].tool_used
            # T0 is not the first tool, so we need to select the first tool
            self._has_first_toolchange = True
            # add line for marking the section
            new_section.append(f'; custom gcode: first_tool_selection\n')
            # if T0 is not used in print, then turn it off
            if not t0_used:
                new_section.append(f'M104 S0 T0 ; turn off T0 as it is not used in print\n')
            # add line for selecting the first tool
            new_section.append(f'T{first_tool} ; select tool {first_tool}\n')
            # add line for marking the section
            new_section.append(f'; custom gcode end: first_tool_selection\n')
            new_section.append('\n')
            # now create a section to contain this and insert it at the start of the linked list
            new_section_section = self._insert_section_after_section(current_section, new_section[0])
            new_section_section.toolchange_gcode = True
            new_section_section.score = self._time_toolchange
            new_section_section.tool = first_tool
            new_section_section.initial_toolchange = True
            self._score_tracker -= new_section_section.score
            # next, replace the lines in the new section
            new_section_section.replace_lines(new_section)

            # next, let's add a preheat section for this tool
            new_section = []
            new_section.append('\n')
            new_section.append(f'; custom gcode: preheat_section T{first_tool}\n')
            new_section.append(f'M104 S{self._tool_configs[first_tool].first_layer_temperature} T{first_tool} ; set tool temperature to preheat\n')
            new_section.append(f'; custom gcode end: preheat_section T{first_tool}\n')
            new_section.append('\n')
            # find the existing start gcode section
            current_section = self._first_section
            while not current_section.start_gcode:
                current_section = current_section.next_section
            new_section_section = self._insert_section_after_section(current_section.prev_section, new_section[0])
            new_section_section.replace_lines(new_section)

    def _process_second_layer_changes(self) -> None:
        """
        Process the second layer changes.
        """
        current_section: GcodeSection
        # first go through all sections and mark them as first_layer_temps_used or other_layer_temps_used
        current_section = self._first_section
        in_first_layer_temps: bool = True
        while current_section is not None:
            if current_section.second_layer_temperature_block:
                in_first_layer_temps = False
            if in_first_layer_temps:
                current_section.first_layer_temps_used = True
            else:
                current_section.other_layer_temps_used = True
            current_section = current_section.next_section

        # next, find the maximum other layer bed temperature for all tools used in the print
        max_other_layer_bed_temp: int = 0
        for tool_config in self._tool_configs:
            if not tool_config.tool_used:
                continue
            if tool_config.bed_temperature > max_other_layer_bed_temp:
                max_other_layer_bed_temp = tool_config.bed_temperature

        # next, find the second layer temperature block
        current_section = self._first_section
        while not current_section.second_layer_temperature_block:
            current_section = current_section.next_section

        # next, create a new section to contain the second layer temperature block
        new_section = []
        # add line for marking the section
        new_section.append(f'\n')
        new_section.append(f'; custom gcode: second_layer_temperature\n')
        # add line for setting bed temperature (without wait)
        new_section.append(f'M140 S{max_other_layer_bed_temp} ; set bed temperature\n')
        # add line for the current tool to be set to the other layer temperature
        new_section.append(f'M104 S{self._tool_configs[current_section.tool].temperature} T{current_section.tool} ; set tool temperature\n')
        # add closing block
        new_section.append(f'; custom gcode end: second_layer_temperature\n')
        new_section.append('\n')
        # now replace the lines in the second layer temperature block
        current_section.replace_lines(new_section)

    def _process_toolchange_sections(self) -> None:
        """
        Process the toolchange sections.
        """
        current_section: GcodeSection
        # go through all sections and find the toolchange sections
        current_section = self._first_section
        skipped_first_toolchange: bool = False
        if not self._has_first_toolchange:
            skipped_first_toolchange = True
        while current_section is not None:
            if current_section.toolchange_gcode and not skipped_first_toolchange:
                skipped_first_toolchange = True
                current_section = current_section.next_section
                continue
            if current_section.toolchange_gcode:
                lines = current_section.resolve_lines()
                # find the outgoing and incoming tool
                for line in lines:
                    if line.startswith('CURRENT_TOOL'):
                        current_section.outgoing_tool = int(line.split('=')[1].strip())
                    if line.startswith('NEXT_TOOL'):
                        current_section.incoming_tool = int(line.split('=')[1].strip())
                # score the section
                current_section.score = self._time_toolchange
                # subtract the score from the total
                self._score_tracker -= current_section.score
                # replace the lines with the T[tool] command
                new_section = []
                # append the first line from the original section
                new_section.append('\n')
                new_section.append(lines[0])
                # append a temperature command for the full temperature depending on whether in first or other layers
                if current_section.first_layer_temps_used:
                    new_section.append(f'M104 S{self._tool_configs[current_section.incoming_tool].first_layer_temperature} T{current_section.incoming_tool} ; set tool temperature\n')
                else:
                    new_section.append(f'M104 S{self._tool_configs[current_section.incoming_tool].temperature} T{current_section.incoming_tool} ; set tool temperature\n')
                # append the T[tool] command for the incoming tool
                new_section.append(f'T{current_section.incoming_tool} ; select tool {current_section.incoming_tool}\n')
                # append a verify tool detected command
                new_section.append(f'VERIFY_TOOL_DETECTED ASYNC=1 ; verify tool detected\n')
                # append the last line from the original section
                new_section.append(lines[-1])
                new_section.append('\n')
                current_section.replace_lines(new_section)
            current_section = current_section.next_section

    def _score_gcode_blocks(self) -> None:
        """
        Score the gcode blocks, these scores are approximated durations.
        """
        current_section: GcodeSection
        # go through all sections and find the gcode blocks to determine line counts
        total_line_count: int = 0
        current_section = self._first_section
        while current_section is not None:
            if current_section.gcode_block:
                # add the line count to the total
                total_line_count += len(current_section.resolve_lines())
            current_section = current_section.next_section

        # next, go through all sections and score them based on the percentage of the total line count
        current_section = self._first_section
        while current_section is not None:
            if current_section.gcode_block:
                # score the section
                current_section.score = (len(current_section.resolve_lines()) / total_line_count) * self._score_tracker
            current_section = current_section.next_section

    def _add_turn_off_tool_logic(self) -> None:
        """
        Add the turn off tool logic, basically when a tool is deselected for the final
        time in the print, we need to turn off the tool and set the temperature to zero.
        """
        current_section: GcodeSection
        # for each tool used in the print, we need to add a section to turn off the tool
        # and set the temperature to zero
        for tool in self._tool_configs:
            if tool.tool_used:
                # first find the last section that uses this tool
                current_section = self._first_section
                while current_section.next_section is not None:
                    current_section = current_section.next_section
                # check if the last section uses this tool
                if current_section.tool == tool.tool_number:
                    # do nothing
                    continue
                # now traverse the sections backwards until we find the last tool change that has this tool as outgoing
                while current_section.prev_section is not None:
                    current_section = current_section.prev_section
                    if current_section.toolchange_gcode:
                        if current_section.outgoing_tool == tool.tool_number:
                            # mark as last deselect
                            current_section.last_deselect = True
                            # get lines from the current section
                            lines = current_section.resolve_lines()
                            # insert a temperature command as the second to last line
                            lines.insert(-2, f'M104 S0 T{tool.tool_number} ; set tool temperature to zero since this tool is no longer used in print\n')
                            # replace the lines in the section
                            current_section.replace_lines(lines)
                            # break out of the loop
                            break

    def _add_deselect_temperature_logic(self) -> None:
        """
        Add the deselect temperature logic.
        """
        # determine if only one extruder is used in the print
        ct_used: int = 0
        for tool in self._tool_configs:
            if tool.tool_used:
                ct_used += 1
        if ct_used == 1:
            # if only one extruder is used in the print, then we can skip the deselect temperature logic
            return
        current_section: GcodeSection
        toolchange_sections: list[GcodeSection] = []
        # go through all sections and find the toolchange sections
        current_section = self._first_section
        while current_section is not None:
            if current_section.toolchange_gcode:
                toolchange_sections.append(current_section)
            current_section = current_section.next_section
        # now go through each toolchange section, determine the temperature to set, and add that to the section
        for toolchange_section in toolchange_sections:
            if toolchange_section.last_deselect:
                # skip if this is the last deselect, it was already handled
                continue
            outgoing_tool = toolchange_section.outgoing_tool
            # now traverse the sections forward, keeping a running total of the score, until we find the next toolchange section where it is selected again
            score_tracker: float = 0.0
            current_section = toolchange_section.next_section
            while current_section is not None:
                if current_section.toolchange_gcode:
                    if current_section.incoming_tool == outgoing_tool:
                        # we found the next toolchange section where the tool is selected again
                        break
                score_tracker += current_section.score
                current_section = current_section.next_section
            if current_section is None:
                # we have reached the end of the print
                break
            # now we can use the score to determine whether to reduce the temperature or turn the heater off
            if score_tracker >= self._tool_configs[outgoing_tool].dormant_time_s:
                # mark the next toolchange section as heat from off
                current_section.heat_from_off = True
                # now add a temperature command to turn the heater off
                lines = toolchange_section.resolve_lines()
                lines.insert(-2, f'M104 S0 T{outgoing_tool} ; turn off tool heater for now as it will not be used again soon\n')
                toolchange_section.replace_lines(lines)
            else:
                # get the current temperature of the tool from the next toolchange section
                next_tool_temp: int
                if current_section.first_layer_temps_used:
                    next_tool_temp = self._tool_configs[outgoing_tool].first_layer_temperature
                else:
                    next_tool_temp = self._tool_configs[outgoing_tool].temperature
                # adjust it by the standby temp delta
                next_tool_temp -= self._standby_temp_delta
                # now add a temperature command to set the temperature
                lines = toolchange_section.resolve_lines()
                lines.insert(-2, f'M104 S{next_tool_temp} T{outgoing_tool} ; set tool temperature to idle temperature\n')
                toolchange_section.replace_lines(lines)

    def _add_preheat_logic(self) -> None:
        """
        Add the preheat logic.
        """

        # determine if only one extruder is used in the print
        ct_used: int = 0
        for tool in self._tool_configs:
            if tool.tool_used:
                ct_used += 1
        if ct_used == 1:
            # if only one extruder is used in the print, then we can skip the preheat logic
            return

        current_section: GcodeSection
        toolchange_sections: list[GcodeSection] = []
        # go through all sections and find the toolchange sections
        current_section = self._first_section
        while current_section is not None:
            if current_section.toolchange_gcode and not current_section.initial_toolchange:
                toolchange_sections.append(current_section)
            current_section = current_section.next_section
        # now for each tool used in the print, excluding the first tool, find the first section it is selected in and mark as heat from off
        first_tool: int = self._first_section.tool
        for tool in self._tool_configs:
            if tool.tool_number == first_tool:
                continue
            if not tool.tool_used:
                continue
            # find the first section it is selected in
            for toolchange_section in toolchange_sections:
                if toolchange_section.incoming_tool == tool.tool_number:
                    # mark the section as heat from off
                    toolchange_section.heat_from_off = True
        # now go through each toolchange section and add the preheat logic
        for toolchange_section in toolchange_sections:
            current_tool: int = toolchange_section.incoming_tool
            # first determine the temperature to set
            temp_to_set: int
            if toolchange_section.first_layer_temps_used:
                temp_to_set = self._tool_configs[current_tool].first_layer_temperature
            else:
                temp_to_set = self._tool_configs[current_tool].temperature
            # next, determine the preheat time needed 
            preheat_time_s: int
            if toolchange_section.heat_from_off:
                preheat_time_s = self._tool_configs[current_tool].warmup_from_off_time_s
            else:
                preheat_time_s = self._tool_configs[current_tool].warmup_time_s
            # now we traverse the sections backwards
            current_section = toolchange_section
            score_tracker: float = 0.0
            while True:
                # add the score of the previous section to the tracker
                score_tracker += current_section.prev_section.score
                # check if there is a previous section
                if current_section.prev_section is None or current_section.prev_section == self._first_section:
                    # we have reached the start of the print
                    # first find the start_print section
                    search_section: GcodeSection = self._first_section
                    while not search_section.start_gcode:
                        search_section = search_section.next_section
                    # if this tool is the first tool, then we can skip the preheat logic
                    if current_tool == first_tool:
                        break
                    # the preheat logic goes at the start of the start_print section
                    preheat_section = self._insert_section_after_section(search_section, '\n')
                    # add the preheat command
                    preheat_section.add_line(f'; custom gcode: preheat_section T{current_tool}\n')
                    preheat_section.add_line(f'M104 S{temp_to_set} T{current_tool} ; set tool temperature to preheat\n')
                    preheat_section.add_line(f'; custom gcode end: preheat_section T{current_tool}\n')
                    preheat_section.add_line('\n')
                    break
                # check if the previous section is a toolchange section
                if score_tracker >= preheat_time_s:
                    # insert the preheat section before the previous section
                    preheat_section = self._insert_section_after_section(current_section.prev_section.prev_section, '\n')
                    preheat_section.add_line(f'; custom gcode: preheat_section T{current_tool}\n')
                    preheat_section.add_line(f'M104 S{temp_to_set} T{current_tool} ; set tool temperature to preheat\n')
                    preheat_section.add_line(f'; custom gcode end: preheat_section T{current_tool}\n')
                    preheat_section.add_line('\n')
                    break
                # move to the previous section
                current_section = current_section.prev_section

    def _reduce_linked_list_to_middle_section(self) -> None:
        """
        Reduce the linked list to the middle section.
        """
        current_section: GcodeSection = self._first_section
        self._middle_section = current_section.resolve_lines()
        while current_section.next_section is not None:
            current_section = current_section.next_section
            self._middle_section = self._middle_section + current_section.resolve_lines()

    def _reconstruct_for_output(self) -> None:
        """
        Reconstructs the output lines list for output.
        """
        self._output_lines = self._output_lines + ['\n']
        self._output_lines = self._output_lines + self._middle_section
        self._output_lines = self._output_lines + ['\n']
        self._output_lines = self._output_lines + self._end_print_section
        self._output_lines = self._output_lines + ['\n']
        self._output_lines = self._output_lines + self._print_stats_section
        self._output_lines = self._output_lines + ['\n']
        self._output_lines = self._output_lines + self._ss_configs_section
    
    def _write_output_file(self) -> None:
        """
        Write the output gcode file.
        """
        with open(self._input_file_path, "w") as writefile:
            for line in self._output_lines:
                writefile.write(line)

    def _insert_new_section_at_end(self, line: str) -> GcodeSection:
        """
        Insert a new section at the end of the sections linked list.
        """
        # check if the list has been initialized
        if self._first_section is None:
            self._first_section = GcodeSection(
                first_line=line,
                tool=self._track_current_tool
            )
            return self._first_section
        # first find the last section
        current_section: GcodeSection = self._first_section
        while current_section.next_section is not None:
            current_section = current_section.next_section
        # create the new section
        new_section = GcodeSection(
            first_line=line,
            tool=self._track_current_tool
        )
        current_section.next_section = new_section
        new_section.prev_section = current_section
        return new_section

    def _insert_new_section_at_start(self, line: str) -> GcodeSection:
        """
        Insert a new section at the start of the sections linked list.
        """
        # create the new section
        old_first_section: GcodeSection = self._first_section
        new_section = GcodeSection(
            first_line=line,
            tool=old_first_section.tool
        )
        new_section.next_section = old_first_section
        old_first_section.prev_section = new_section
        self._first_section = new_section
        return new_section

    def _insert_section_after_section(self, section: GcodeSection, line: str) -> GcodeSection:
        """
        Insert a new section after a given section.
        """
        new_section = GcodeSection(
            first_line=line,
            tool=section.tool
        )
        new_section.next_section = section.next_section
        section.next_section.prev_section = new_section
        section.next_section = new_section
        new_section.prev_section = section
        return new_section

    def _delete_section(self, section: GcodeSection) -> None:
        """
        Delete a section from the linked list.
        """
        section.prev_section.next_section = section.next_section
        section.next_section.prev_section = section.prev_section



def main(args) -> None:
    """
    Post process gcode file.

    :param args: command line arguments
    """
    if len(sys.argv) > 1:
        print(f"Path to file provided: {sys.argv[1]}")
    else:
        print("No file path provided, exiting now.")
        sys.exit(1)
    
    processor: ToolchangerPostprocessor = ToolchangerPostprocessor(sys.argv[1])
    processor.process_gcode()

main(sys.argv)