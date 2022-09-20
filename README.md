# Python GIF Parser

Extremely slow pure Python GIF parser - all of the fun and none of the profit. Originally intended as a launching point for Python GUI experimentation. Became a learning experience after discovering GIFs taking 30+ seconds to decode.

## Benchmarks

Python 3.10.2 64-bit on Intel i5 laptop

| Test Image | Size | Frames | Execution Time (s) |
| --- | --- | --- | --- |
| test1.gif | 10x10 | 1 | 0.00074 |
| test2.gif | 11x29 | 3 | 0.00131 |
| test3.gif | 599x600 | 1 | 0.58798 |
| [test4.gif](https://c.tenor.com/DKsQ9JoQt7EAAAAC/angry-panda.gif) | 450x338 | 23 | 3.64672 |

## Credit

Thanks to [Matthew Flickinger's 'What's in a GIF'](https://www.matthewflickinger.com/lab/whatsinagif/) for teaching me about the guts of the GIF and for the test files
