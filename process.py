#!/usr/bin/python
import sys
from shutil import ReadError


CFG_DEFAULT_TIME_BEFORE_PREHEAT_S: int = 60
CFG_DEFAULT_OFF_TIME_TO_GO_DORMANT_S: int = 120



class ToolConfig:
    bed_temperature: int
    first_layer_bed_temperature: int
    temperature: int
    first_layer_temperature: int
    chamber_temperature: int


'''
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE
TODO: STOPPED HERE

NOTE: remember, if it is not used, then don't implement it, only once used
and there are things listed here that are not used, so don't implement them
without verifying that they are needed

NOTE NOTE NOTE: starting notes
- start section: 
    - TODO: still need to sort this out
    - the section parsing will still have a "virtual" section at the head of the list
      this is to keep it consistent for the algorithm
    - this section will also handle the initial preheating, temp setting, etc so that the algo
      described below can just begin running as if there was a previous section
    - this work will be done by first chopping off the start and setting it aside, then doing
        this work, then doing the start because the other work was necessary to do the start


- start with raw lines with both ends chopped off, basically first printing to last printing
- filtered down such that all that remains are:
    - actual gcode commands
    - custom gcode blocks
    - layer change comments
    - exclude object commands


- next break it into sections which are groups of lines
- section breaks occur at:
    - the start obviously
    - the end obviously
    - layer changes
    - custom gcode blocks
    - really any non g-code line, including:
        - EXCLUDE_OBJECT_START
        - EXCLUDE_OBJECT_END
        - M73 lines, you can also probably get information from these as they give estimates 
          on % complete and time remaining
            - TODO this, because you can just assume the slicer knew better and then use these
              for interpolating the score for the sections in between M73 commands TODO this
        - any other non movement gcode lines

- store the sections in a class consisting of:
    - the actual lines in the section
    - whether the section is scored or not/the score of the section
    - the tool for the section (reference to the tool config)
    - the layer number for the section
    - the layer height for the section
    - the approximate duration of the section
    - there will be special fields for the different types of custom gcode blocks
    - the index of the section in the list of sections
    - if the section is virtual (meaning not kept, really this means the artificially added section for the start tool selection)

- store these in a LINKED list of sections

- next, you can create a list of sections that are for tool changes

- then for each tool change you determine:
    - for outgoing tool:
        - is off?
        - is dormant?
        - etc
    - for incoming tool:
        - when to preheat?
        - etc
    - these all result in actions, each of which has a calculated position
    - each action results in the creation of a new section for the action
    - these are inserted into the sections linked list, and split whichever section they land on 
        in two, with this one inserted in between
            - this is necessary because otherwise it messes up your ability to accurately 
                split sections with action sections

- finally, you can reconstruct the gcode file from the linked list of sections

- next, you will have enough information to do an intelligent start section

TODO: add to the start filament custom gcode section the preheat time for the tool
TODO: ^ this!
TODO: ^ this!
TODO: ^ this!
TODO: ^ this!

TODO: need to make this configurable, create a config file

TODO: when you print multicolor no T0, there's nothing forcing a start with T0, that should 
definitely be forced here, or otherwise you can just do it in your macro, no no, let's force 
it here AND encourage folks to do it in macros

TODO: on the same note of setting the warmup time, you could easily use this or another post
process script to define extra variables then make them available to the user in the custom 
gcode section. This script could do replacement based on what the user puts. Sort of a way to 
extend the slicer's capabilities.
    Like, for example, you could make this script allow the user to use prusaslicer's is 
    tool used variable, well, they'd have to do it as a comment to not piss off the slicer, 
    but that's fine and easy enough of an ask.

'''



class ToolchangerPostprocessor:

    _input_file_path: str
    _raw_lines: list[str]
    _output_lines: list[str]

    # print stats
    _layer_count: int
    _print_time_s: int

    # relevant ss configs
    _first_layer_height: float
    _tool_count_overall: int
    _tool_configs: list[ToolConfig]

    # tracking
    _tools_used: list[int]

    # sections
    _end_print_section: list[str]
    _print_stats: list[str]
    _ss_configs: list[str]

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
        self._print_stats = []
        self._ss_configs = []

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
    
    def _write_output_file(self) -> None:
        """
        Write the output gcode file.
        """
        with open(self._input_file_path, "w") as writefile:
            for line in self._output_lines:
                writefile.write(line)




    def process_gcode(self) -> None:
        """
        Process the gcode file.
        """
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

        # extract end print section
        self._extract_end_gcode_section()
        # process end print section
        self._process_end_gcode_section()

        # find tools used in print
        self._find_tools_used_in_print()
        # eliminate ss pre toolchange tool temp drop
        self._eliminate_ss_pre_toolchange_tool_temp_drop()

        # # TODO: temp
        for line in self._raw_lines:
            self._output_lines.append(line)
        # # TODO: temp

        self._reconstruct_for_output()
        self._write_output_file()

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
        self._ss_configs = self._raw_lines[idx_begin:idx_end + 1]
        # then remove these lines from the raw lines list
        self._raw_lines = self._raw_lines[:idx_begin] + self._raw_lines[idx_end + 1:]

    def _parse_slicer_configs(self) -> None:
        """
        Parse the slicer configs section to extract relevant configs at the top level
        as well as on a per-tool basis.
        """
        # first_layer_height
        for line in self._ss_configs:
            if line.startswith('; first_layer_height ='):
                self._first_layer_height = float(line.split('=')[1].strip())
                break
        # find overall tool count using bed_temperature
        for line in self._ss_configs:
            if line.startswith('; bed_temperature ='):
                self._tool_count_overall = len(line.split(','))
                break
        # create empty tool configs list
        self._tool_configs = [ToolConfig() for _ in range(self._tool_count_overall)]
        # parse individual tool_configs
        # parse bed temperature
        for line in self._ss_configs:
            if line.startswith('; bed_temperature ='):
                bed_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(bed_temperatures):
                    self._tool_configs[i].bed_temperature = int(temp)
                break
        # parse chamber temperature
        for line in self._ss_configs:
            if line.startswith('; chamber_temperature ='):
                chamber_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(chamber_temperatures):
                    self._tool_configs[i].chamber_temperature = int(temp)
                break
        # parse first_layer_bed_temperature
        for line in self._ss_configs:
            if line.startswith('; first_layer_bed_temperature ='):
                first_layer_bed_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(first_layer_bed_temperatures):
                    self._tool_configs[i].first_layer_bed_temperature = int(temp)
                break
        # parse first_layer_temperature
        for line in self._ss_configs:
            if line.startswith('; first_layer_temperature ='):
                first_layer_temperatures = line.split('=')[1].strip().split(',')
                for i, temp in enumerate(first_layer_temperatures):
                    self._tool_configs[i].first_layer_temperature = int(temp)
                break
        # parse temperature
        for line in self._ss_configs:
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
        self._print_stats = output

    def _parse_print_stats(self) -> None:
        """
        Parse the print stats section.
        """
        # parse layer count
        for line in self._print_stats:
            if line.startswith('; layer count:'):
                self._layer_count = int(line.split(':')[1].strip())
                break
        # parse print time to get minutes and seconds then convert to seconds
        print_time_line: str = ''
        for line in self._print_stats:
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

    def _eliminate_blank_lines(self) -> None:
        """
        Eliminate blank lines from the raw lines list.
        """
        self._raw_lines = [line for line in self._raw_lines if line.strip()]

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
    
    def _process_end_gcode_section(self) -> None:
        """
        Process the end print section.

        The only thing needed here is to remove the current tool line that is at the
        start of each end_filament_gcode subsection
        """
        output_lines: list[str] = []
        prev_line_is_end_filament_gcode: bool = False
        for line in self._end_print_section:
            if line.startswith('; custom gcode: end_filament_gcode'):
                prev_line_is_end_filament_gcode = True
            elif prev_line_is_end_filament_gcode:
                prev_line_is_end_filament_gcode = False
                continue
            output_lines.append(line)
        self._end_print_section = output_lines

    def _find_tools_used_in_print(self) -> None:
        """
        Find the tools used in the print.
        """
        self._tools_used = []
        for tool in range(self._tool_count_overall):
            for line in self._raw_lines:
                tool_name = f'T{tool}'
                if tool_name in line:
                    self._tools_used.append(tool)
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





    def _reconstruct_for_output(self) -> None:
        """
        Reconstructs the raw lines list for output.
        """
        # TODO: sections that come before this

        # add the end print section
        self._output_lines = self._output_lines + self._end_print_section


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
    
    # processor: ToolchangerPostprocessor = ToolchangerPostprocessor(sys.argv[1])
    # processor.process_gcode()

main(sys.argv)