#!/usr/bin/python
import sys
from shutil import ReadError

class ToolchangerPostprocessor:

    _input_file_path: str
    _raw_lines: list[str]
    _output_lines: list[str]


    def __init__(self, input_file_path: str) -> None:
        """
        Initialize the ToolchangerPostprocessor class.

        :param input_file_path: path to the input gcode file
        """
        self._input_file_path = input_file_path
        self._output_lines = []
        self._raw_lines = self._read_input_file()        

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

    def _eliminate_ss_pre_toolchange_tool_temp_drop(self) -> None:
        """
        Eliminate the ss-inserted pre toolchange tool temp drop.
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


    def process_gcode(self) -> None:
        """
        Process the gcode file.
        """
        self._eliminate_ss_pre_toolchange_tool_temp_drop()
        for line in self._raw_lines:
            self._output_lines.append(line)
        self._write_output_file()


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