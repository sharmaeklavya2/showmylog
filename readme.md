# ShowMyLog

I log all my daily activities in fixed-format text files.
The script `showmylog.py` helps me analyze them.

I use a text editor to create an input file
(see [example.mylog](https://github.com/sharmaeklavya2/showmylog/blob/master/example.mylog)).
Then I run `showmylog.py` on the input file.
It prints a summary of my activities on screen
(see [output.txt](https://sharmaeklavya2.github.io/showmylog/output.txt) for example)
and outputs an HTML report
(see [report.html](https://sharmaeklavya2.github.io/showmylog/report.html) for example).
The report contains a timeline-diagram where you can hover over intervals to see details.

### How logging helps

I started logging all my activities a few years ago.
This has these advantages:

* I wanted to increase my productivity.
  If I can find out how much productive and non-productive work I do everyday,
  and how much time different activities take,
  I can make changes to my routine accordingly to optimize productive work.

* Maintaining a log has become a habit and now I'm often constantly aware of what I'm doing.
  This has helped me become more productive.

* I have a record of my past activities. If I can't recall what I did a few days ago,
  or I can't recall when I last did something, my log helps me find out.

### Log file format considerations

Initially I used notebooks made of paper to do this, but I soon switched to text files.
This was better since edits were less messy and I could `grep` those files.

I needed a machine-readable format so that I could do automated or semi-automated analysis on it.
But I also needed a format which is not tied to a particular program, so these files must be human-readable
and editable with a simple text editor.

### Log file format details

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

You can see [`example.mylog`](example.mylog) for an example of a log file.

### Additional constraints imposed on format by `showmylog.py`

* No two activities should overlap.
* All activities should be in chronological order.
* `duration` should be equal to `end_time` - `start_time`.

### What does `showmylog.py` do?

* Does basic validation of log files.
* Displays duration sums after grouping on `work_type` and `(work_type, label)`.
* Creates a timeline visualization of the log in HTML.

Run `./showmylog.py --help` for more info.

Currently `showmylog.py` has no way of handling uncertainty.
It replaces all `?` by `0` in times.

### Code

This code is written for python 3.5 and above.
It contains [PEP 484 type annotations](https://www.python.org/dev/peps/pep-0484/),
which makes it possible to use [mypy](http://mypy-lang.org/) for static type-checking.
`showmylog.py` passes the `--strict` mypy test.

### Usage tips

Add this line to your `~/.vimrc` to enable syntax highlighting for mylog files:

    au BufRead,BufNewFile *.mylog set filetype=diff

I store my files in `~/mylog/`. Each file has a name of the form `YYYY-MM-DD.mylog`.

These are some handy bash aliases:

    alias today='date "+%F"'
    alias yesterday='date -d "yesterday" "+%F"'
    alias logit='vim ~/mylog/$(today).mylog'
    alias logyes='vim ~/mylog/$(yesterday).mylog'
