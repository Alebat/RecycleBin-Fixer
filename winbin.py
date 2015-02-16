from argparse import ArgumentParser
import os
from shutil import move, rmtree

__author__ = 'AleB'
__version__ = "0.0.1.0"

nwin = (os.name != "nt" and os.name != "ce")

class BColors:
    HEADER = '\033[95m' if nwin else ''
    OK_BLUE = '\033[94m' if nwin else ''
    OK_GREEN = '\033[92m' if nwin else ''
    WARNING = '\033[93m' if nwin else ''
    FAIL = '\033[91m' if nwin else ''
    END_C = '\033[0m' if nwin else ''


class Bin(object):
    index_size = 544
    index_name_p = 24
    preamble = "\01\0\0\0\0\0\0\0"
    integrity_report = ['missing_trash', 'missing_indexes', 'wrong_sized_indexes', 'wrong_preamble_indexes']

    @classmethod
    def _file_start(cls, f):
        with open(f, "rb") as ff:
            return ff.read(len(cls.preamble)) == cls.preamble

    @classmethod
    def _read_path(cls, f):
        with open(f, "rb") as ff:
            ff.read(cls.index_name_p)
            return bytes(ff.read(cls.index_size - cls.index_name_p)).decode(encoding="utf-16").rstrip('\00')

    def __init__(self, bin_dir):
        self.dir = bin_dir
        self.users = []
        self.indexes = {}
        self.files = {}
        self.original_paths = {}
        self.tree = {}

    def load_data(self):
        self.users = [x for x in os.listdir(self.dir) if os.path.isdir(os.path.join(self.dir, x))]
        for i in self.users:
            self.indexes[i] = [x for x in os.listdir(os.path.join(self.dir, i)) if x[0:2] == "$I"]
            self.files[i] = [x for x in os.listdir(os.path.join(self.dir, i)) if x[0:2] == "$R"]
            self.original_paths[i] = {}
            for x in self.indexes[i]:
                self.original_paths[i][x] = self.__class__._read_path(os.path.join(self.dir, i, x))

    def get_file(self, i, user):
        if i in self.indexes[user]:
            return "$R" + i[2:]
        else:
            raise KeyError(i + " not in " + user + "'s indexes")

    def missing_trash(self, user):
        return [i for i in self.indexes[user] if not ("$R" + i[2:]) in self.files[user]]

    def missing_indexes(self, user):
        return [i for i in self.files[user] if not ("$I" + i[2:]) in self.indexes[user]]

    def wrong_sized_indexes(self, user):
        return [i for i in self.indexes[user]
                if os.stat(os.path.join(self.dir, user, i)).st_size != Bin.index_size]

    def wrong_preamble_indexes(self, user):
        return [i for i in self.indexes[user]
                if self.__class__._file_start(os.path.join(self.dir, user, i))]

    def report_integrity(self, user):
        a = {}
        for r in Bin.integrity_report:
            x = self.__class__.__getattribute__(self, r)(user)
            if len(x) > 0:
                a[r] = x
        return a

    def build_tree(self, sep='\\'):
        for u in self.users:
            self.tree[u] = {}
            for f in self.original_paths[u]:
                self.__class__._store(self.tree[u], self.original_paths[u][f].split(sep))

    @classmethod
    def _store(cls, r, p):
        if len(p) > 0:
            if not p[0] in r:
                r[p[0]] = {}
            if len(p) > 1:
                cls._store(r[p[0]], p[1:])
            else:
                r[p[0]] = None

    @classmethod
    def _tree_get(cls, r, p):
        try:
            if len(p) > 0:
                if len(p) > 1:
                    t = cls._tree_get(r[p[0]], p[1:])
                else:
                    t = r[p[0]]
            else:
                t = r
        except ValueError:
            return []
        else:
            return t

    def tree_get(self, p):
        y = self.__class__._tree_get(self.tree, p)
        if y is None:
            return []
        else:
            if len(p) == 0:
                return [(False, x) for x in y]
            else:
                return [('\\'.join(p[1:] + [x]) in self.original_paths[p[0]].values(), x) for x in y]

    def recovery(self, l):
        r = [x for x in self.original_paths[l[0]] if self.original_paths[l[0]][x] == '\\'.join(l[1:])]
        if len(r) == 1:
            dst = os.path.join(os.path.dirname(os.path.abspath(self.dir)), '/'.join(l[2:]))
            print(BColors.WARNING + "Recovering:", r[0], ':', '\\'.join(l[1:]), BColors.END_C)
            print(BColors.WARNING, "In: ", dst, BColors.END_C, sep="")
            move(os.path.join(self.dir, l[0], self.get_file(r[0], l[0])), dst)
            d = os.path.join(self.dir, l[0], r[0])
            if os.path.isfile(d):
                os.remove(d)
            else:
                rmtree(d)
            self.load_data()
            self.build_tree()
        elif len(r) == 0:
            print(BColors.FAIL, "No indexes for: ", '\\'.join(l[1:]), BColors.END_C, sep="")
        else:
            print(BColors.FAIL, "Multiple indexes for: ", '\\'.join(l[1:]), BColors.END_C, sep="")


def check_integrity(b):
    for u in b.users:
        x = b.report_integrity(u)
        print("Bin of " + BColors.HEADER + u + BColors.END_C)
        if len(x) > 0:
            print(BColors.WARNING + "WARNING: Failed integrity check:", BColors.END_C)
            for i in x.keys():
                print(i)
                print(x[i])
        else:
            print(BColors.OK_GREEN + "Integrity OK" + BColors.END_C)


def check_arguments():
    ap = ArgumentParser()
    ap.description = 'WinBin v' + __version__ + '\nManages the >= Microsoft Windows Vista Recycle Bin.'
    ap.add_argument("-d", "--directory", default="", help="The $Recycle.Bin\<SID> directory")
    ap.add_argument("-n", "--navigate", action="store_true", default=False, help="Enters the navigation mode")
    # TODO: Shows elements that were in the specified path.
    a = ap.parse_args()
    if a.directory == "" and not a.navigate:
        ap.print_usage()
    if a.directory != "" and not os.path.exists(a.directory):
        print(BColors.FAIL + "Specified directory does not exist (maybe wrong or maybe volume not mounted)." +
              BColors.END_C)
    return a


def navigate_through(b):
    print("Use the code to open or '..' to close the folder.\nUse 'rec N' to recover a file.")
    l = []
    while True:
        c = b.tree_get(l)
        if len(c) == 0:
            del l[-1]
            continue
        for i, (k, j) in enumerate(c):
            print(BColors.END_C + str(i+1), (BColors.END_C if k else BColors.OK_BLUE) + j + BColors.END_C, '\t')
        x = input(BColors.HEADER)
        try:
            x = int(x)
        except ValueError:
            if x == "..":
                if len(l) > 0:
                    del l[-1]
            elif x[0:3] == "rec" and len(l) > 0:
                try:
                    y = int(x[3:])-1
                except ValueError:
                    pass
                else:
                    if y < len(c):
                        j, k = c[y]
                        b.recovery(l + [k])
        else:
            if x <= len(c):
                j, k = c[x-1]
                l.append(k)
    print(BColors.END_C)


def main():
    if not nwin:
        print("!!! Note that this script was not designed to work on Windows\nColours highlightings are disabled.\n")
    a = check_arguments()
    b = Bin(a.directory if a.directory != "" else ".")
    if a.directory != "":
        b.load_data()
        check_integrity(b)
    if a.navigate:
        b.build_tree()
        navigate_through(b)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(BColors.END_C, "\nKeyboardInterrupt")
