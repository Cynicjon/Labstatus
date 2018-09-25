import time
import datetime
import ctypes
import os
from collections import deque
from threading import Lock, Thread
try:
    from watchdog import events, observers
    from colorama import Fore, Style, init as colorama_init
except ModuleNotFoundError:
    input("Please install the requirements! \nPress Enter to exit.")
    quit()


class LabHandler(events.PatternMatchingEventHandler):  # inheriting from watchdog's PatternMatchingEventHandler
    patterns = ["*.xdrx", "*.eds"]                              # events are only generated for these file types.
    recent_events = deque('ghi', maxlen=30)  # A queue of 30 recent events to prevent duplicate events. 30 is arbitrary.
    _q_cnt = 0
    _v_cnt = 0
    viia7_str = Fore.CYAN + 'Viia7' + Style.RESET_ALL + ':  '       # Colour codes for Viia7.
    qiaxcel_str = Fore.MAGENTA + 'Qiaxcel' + Style.RESET_ALL + ':'  # Colour codes for Qiaxcel
    """
    The Observer passes events to the handler, which then calls functions based on the type of event
    Event object properties:
    event.event_type
        'modified' | 'created' | 'moved' | 'deleted'
    event.is_directory
        True | False
    event.src_path
        path/to/observed/file
    """

    def on_modified(self, event):
        """Called when a modified event is detected. aka Viia7 events."""
        time.sleep(1)  # wait here to allow file to be fully written - prevents some errors with os.stat
        if '.eds' in event.src_path and event.src_path not in self.recent_events:  # .eds files we haven't seen recently
            if self.is_large_enough(event.src_path):  # this is here instead of ^ to prevent double error message
                with v_lock:        # TODO handle large enough exception here instead?
                    self._v_cnt = self.notif(event, self._v_cnt)

    def on_created(self, event):
        """Called when a new file is created. aka Qiaxcel events."""
        if '.xdrx' in event.src_path and event.src_path not in self.recent_events:  # .xdrx file we haven't seen
            with q_lock:
                self._q_cnt = self.notif(event, self._q_cnt)

    def notif(self, event, _x_cnt):
        """Prints a notification about the event to console. May be normal or distinguished.
         Distinguished notifications flash the console window.
         Notif will be distinguished if users windows login is in path or _x_cnt = 1 or > 9 (now/ always setting)"""
        self.recent_events.append(event.src_path)  # Add to recent events queue to prevent duplicate notifications.
        machine, file = self.get_event_info(event)
        if os.getlogin() in event.src_path.lower() or _x_cnt == 1 or _x_cnt > 9:  # distinguished notif
            file = Fore.GREEN + file + Style.RESET_ALL      # file name in green
            message = Fore.GREEN + '>>> {}'.format(machine).ljust(21, ' ') + ' {} has finished!'.format(file)
            ctypes.windll.user32.FlashWindow(ctypes.windll.kernel32.GetConsoleWindow(), True)  # Flash console window
        else:                                               # non distinguished notification
            file = Style.BRIGHT + file + Style.RESET_ALL    # file name in white
            message = ' -  {}'.format(machine).ljust(21, ' ') + ' {} has finished.'.format(file)
        print(self.bright_time() + message)
        if _x_cnt == 1:         # If this was the run to notify on, inform that notification is now off.
            print(''.ljust(19, ' ') + machine + ' No longer notifying.')
        return _x_cnt-1         # Increment counter down

    @staticmethod
    def notify_setting(machine, _x_cnt):
        """Prints the current Notify setting"""
        if 0 < _x_cnt < 10:
            return ''.ljust(19, ' ') + machine + ' Notifying in ' + str(_x_cnt) + ' runs time'  # change this
        if _x_cnt > 9:
            return ''.ljust(19, ' ') + machine + ' Notifying for all runs'
        elif _x_cnt < 1:
            return ''.ljust(19, ' ') + machine + ' Notify OFF'  # change this

    @property
    def q_cnt(self):
        return self.notify_setting(self.qiaxcel_str, self._q_cnt)

    @q_cnt.setter
    def q_cnt(self, x):
        """Toggles Notify setting if 0 : Always notify (x > 9) / Don't notify (x <= 0)"""
        if x == 0:
            self._q_cnt = 0 if self._q_cnt > 0 else 1337
        else:
            self._q_cnt = x

    @property
    def v_cnt(self):
        return self.notify_setting(self.viia7_str, self._v_cnt)

    @v_cnt.setter
    def v_cnt(self, x):
        if x == 0:
            self._v_cnt = 0 if self._v_cnt > 0 else 1337
        else:
            self._v_cnt = x

    def get_event_info(self, event):
        """Returns the machine name and file path."""
        machine = self.viia7_str if event.event_type == 'modified' else self.qiaxcel_str
        file = str(os.path.splitext(event.src_path)[0].split('\\')[-1])  # Get file name
        return machine, file

    @staticmethod
    def bright_time():
        """Returns the current time formatted nicely, flanked by ANSI escape codes for bright text."""
        return Style.BRIGHT + time.strftime("%d.%m.%y %H:%M ", time.localtime()) + Style.NORMAL

    def is_large_enough(self, path):
        """Determines if the file given by path is above 1300000 bytes"""
        try:
            return os.stat(path).st_size > 1300000
        except (FileNotFoundError, OSError) as e:
            file = str(os.path.splitext(path)[0].split('\\')[-1])
            print(Fore.RED, e, Style.RESET_ALL)  # If not, print error and assume True.
            print(self.bright_time() + ' -  {}'.format(self.viia7_str).ljust(21, ' ') + file + " wasn't saved properly!"
                  " You'll need to analyse and save the run again from the machine.")
            return True  # Better to inform than not. I think this happens when .eds isn't saved or is deleted?


def get_input():
    """A loop that asks user for input. Responds to q (Qiaxcel), v (Viia7) and a single number or some combination.
    Any digit after the first is ignored. e.g: q, q5, v4, qv3. q54 == q5.
    no number will toggle notify all, a number will notify after n events."""
    try:
        while True:
            inp = input('')
            if inp == 'help':
                print('Monitors Qiaxcel and Viia7 for file events and prints a notification.\n'
                      'Files with your username in the path will generate a distinguished notification.\n'
                      'Commands may be given to notify you on other events, e.g. All runs or in n run\'s time.\n')
                print('Commands - q (Qiaxcel), v (Viia7) and a single digit or some combination.\n'
                      'Any digit after the first is ignored. e.g: q, q5, v4, qv3. q54 == q5.\n'
                      'No number will toggle notifications on all events, a number will notify after n events.\n')
            for char in inp:
                if char.isdigit():          # if a digit is in input, set count = that digit and break.
                    count = int(char)
                    break                   # break out of loop. Only detects first digit in string - intentionally.
            else:
                count = 0
            if 'q' in inp.lower():
                with q_lock:                # lock to make referencing variable shared between threads safe.
                    labhandler.q_cnt = count
                    print(labhandler.q_cnt)
            if 'v' in inp.lower():
                with v_lock:
                    labhandler.v_cnt = count
                    print(labhandler.v_cnt)
    except EOFError:                        # This error is given when exiting script only. Ignore.
        pass


def viia7_path(last=False):
    makedirs = True
    date = datetime.date.today()
    if last:
        makedirs = False
        first = date.replace(day=1)                     # replace the day with the first of the month.
        date = first - datetime.timedelta(days=1)       # subtract one day to get the last day of last month
    month, year = date.strftime('%b %Y').split(' ')
    path = build_path(month, year)
    if os.path.isdir(path):
        return path
    month_full = date.strftime('%B')
    path2 = build_path(month_full, year)
    if os.path.isdir(path2):
        return path2
    if month == 'Sep':
        path2 = build_path('Sept', year)
        if os.path.isdir(path2):
            return path2
    if makedirs:
        os.makedirs(path, exist_ok=True)
        return path
    print("Cant find last month's Viia7 Path")
    raise FileNotFoundError


def build_path(month, year):
    return '\\\File01-s0\Team121\Genotyping\qPCR ' + year + '\Experiments\\' + month + ' ' + year


if __name__ == '__main__':
    colorama_init()            # Init colorama to enable coloured text output via ANSI escape codes on windows console.
    q_lock = Lock()            # Locks used when reading or writing q_cnt or v_cnt since they are in multiple threads.
    v_lock = Lock()

    current_month_year = time.strftime("%b %Y", time.localtime())  # This is checked later to see if month changed.
    qiaxcel = '\\\File01-s0\Team121\Genotyping\QIAxcel\Experiment\Dna'
    viia7 = viia7_path()                                # Path to current month Viia7 experiments.
    viia7last = viia7_path(last=True)                   # Path to last month Viia7 experiments.
    labhandler = LabHandler()                           # Instantiate Handler
    observer = observers.Observer()                     # Instantiate Observer
    observer.schedule(labhandler, path=qiaxcel)         # Schedule locations to watch, and to use our Handler.
    viia7watch_last = observer.schedule(labhandler, path=viia7last)
    viia7watch_curr = observer.schedule(labhandler, path=viia7)
    observer.start()                                    # Start Observer thread.

    print('Running...')
    print('Enter a command or type help')
    input_loop = Thread(target=get_input)
    input_loop.start()                                  # Start a new thread to get user input.
    try:
        while True:  # Check if month has changed every 1 hr.
            if current_month_year != time.strftime("%b %Y", time.localtime()):  # If month has changed.
                current_month_year = time.strftime("%b %Y", time.localtime())   # Update month
                print('The month has changed to ' + current_month_year)
                viia7 = viia7_path()                                            # Get new viia7 path
                observer.unschedule(viia7watch_last)                            # Unschedule last month watch
                viia7watch_last = viia7watch_curr                               # Make current month watch last month
                viia7watch_curr = observer.schedule(labhandler, viia7)          # Schedule new current month
            time.sleep(3600)                                                    # Check every hour.
    except KeyboardInterrupt:                                                   # on keyboard interrupt (Ctrl + C)
        observer.stop()                                                         # Stop observer + Threads.
        input_loop.join()
        print('\nbye!')
    observer.join()
    input_loop.join()
