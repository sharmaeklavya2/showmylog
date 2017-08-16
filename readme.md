# ShowMyLog

I log my life in fixed-format text files. The script `showmylog.py` helps me analyze them.

### How logging helps

I started logging all my activities a few years ago.
This has these advantages:

* I wanted to increase my productivity. As every good software developer knows, we must
  <a href="https://en.wikipedia.org/wiki/Profiling_(computer_programming)">profile</a> before optimizing.
  That is, I should know how much productive and non-productive work I do everyday
  before I start making changes to my routine to optimize productive work.

* Maintaining a log has become a habit and now I'm constantly aware of what I'm doing.
  This has helped me become more productive.

* I have a record of my past activities. If I can't recall what I did a few days ago,
  or I can't recall when did I last do something, my log helps me find out.

### Logging format

Initially I used notebooks made of paper to do this.
But I did it in a somewhat tabular form, which was cumbersome on paper.

So I started doing it in text files instead.
This was better since edits were less messy and I could `grep` those files.
But I needed something more.

I needed a machine-readable format so that I could do automated or semi-automated analysis on it.
But I also needed a format which is not tied to a particular program, so these files must be human-readable
and editable with a simple text editor.

Some people have suggested that there should be a script to which I can send start and stop commands
and it will automatically add entries to log files.
This is a good idea but I haven't implemented it yet and I don't think that is worth the effort.
For now, I manually add entries to log files using a text editor.

### Logging format details

A file is made up of records.
Each record should span just one line.
Anything after a `#` will be treated as a comment and ignored.
There can be empty lines in the file.

Each record should be of this form:

    work_type start_time end_time penalty duration label sublabel description

None of these parts should have spaces, except `description`.

* `work_type` can be any string, but I prefer keeping it a single-character string. Currently, I use these strings:
  - `+`: Positive work, like study or exercise.
  - `-`: Negative work, like wasting time on the internet or talking to friends about useless stuff.
  - `!`: Partially negative work.
  - `:`: Non-productive but necessary work, like eating, bathing, shopping for groceries.
  - `s`: Sleeping.
  - `u`: Unaccounted, i.e. time intervals not covered by a log file.
    I never use it, but `showmylog.py` reports unaccounted time under this `work_type`.
* `start_time`, `end_time`, `penalty` and `duration` should either be `-:--` or `--:--` or
  it should match the regex `[\d?]{1,2}:[\d?]{2}`. The symbol `?` denotes uncertainty.
  `duration` should be less than or equal to `end_time` minus `start_time`.
* `label` and `sublabel` are used to identify a certain type of work.
  `sublabel` can be empty.
* `description` can be anything. It can also be empty.

I use the `mylog` file extension for these files.
I have set `syntax=diff` for `mylog` files in vim, so that lines are colored appropriately.

You can see [`example.mylog`](example.mylog) for an example of a log file.

### Limitations imposed on format by `showmylog.py`

* No two activities should overlap.
* All activities should be in chronological order.
* `duration` should be equal to `end_time` - `start_time`.

### What does `showmylog.py` do?

* Does basic validation of log files.
* Displays duration sums after grouping on `work_type` and `(work_type, label)`.
* Creates a timeline visualization of the log in HTML.

Run `./showmylog.py --help` for more info.

### Code

This code is written for python 3.5 and above.
It contains [PEP 484 type annotations](https://www.python.org/dev/peps/pep-0484/),
which makes it possible to use [mypy](http://mypy-lang.org/) for static type-checking.
`showmylog.py` passes the `--strict-optional` mypy test.
