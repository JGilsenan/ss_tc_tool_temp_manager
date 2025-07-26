#!/usr/bin/python
import sys
from shutil import ReadError

class ToolchangerPostprocessor:

    _input_file_path: str
    _raw_lines: list[str]
    _output_lines: list[str]


    def __init__(self, input_file_path: str) -> None:
        self._input_file_path = input_file_path
        self._output_lines = []
        self._raw_lines = self.read_input_file()
        # print(self._raw_lines)
        self.testthing()
        

    def read_input_file(self) -> list[str]:
        try:
            print(f"Reading file: {self._input_file_path}")
            with open(self._input_file_path, "r", encoding='UTF-8') as readfile:
                return readfile.readlines()
        except ReadError as exc:
            print('FileReadError:' + str(exc))
            sys.exit(1)
        
    def testthing(self) -> None:
        for i in range(25):
            self._output_lines.append('; hello\n')
        for line in self._raw_lines:
            self._output_lines.append(line)
        with open(self._input_file_path, "w") as writefile:
            for line in self._output_lines:
                writefile.write(line)




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
    

main(sys.argv)