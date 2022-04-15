#!/usr/bin/env python3
#
# unit tests for debugger

import os
import sys
import time
import platform
import threading
import subprocess
import unittest

from binaryninja import BinaryView, BinaryViewType, LowLevelILOperation
from binaryninja.debugger import DebuggerController, DebugStopReason


# 'helloworld' -> '{BN_SOURCE_ROOT}\public\debugger\test\binaries\Windows-x64\helloworld.exe' (windows)
# 'helloworld' -> '{BN_SOURCE_ROOT}/public/debugger/test/binaries/Darwin/arm64/helloworld' (linux, macOS)
def testbin_to_fpath(testbin, arch=None, os_str=None):
    if arch is None:
        arch = platform.machine()

    if os_str is None:
        os_str = platform.system()

    if os_str == 'Windows' and not testbin.endswith('.exe'):
        testbin += '.exe'

    base_path = os.path.dirname(os.path.realpath(__file__))
    path = os.path.realpath(os.path.join(base_path, 'binaries', f'{os_str}-{arch}', testbin))
    return path


def is_wow64(fpath):
    if 'x86' not in fpath:
        return False
    a, b = platform.architecture()
    return a == '64bit' and b.startswith('Windows')


class DebuggerAPI(unittest.TestCase):

    def setUp(self) -> None:
        self.arch = ''

    def test_repeated_use(self):
        fpath = testbin_to_fpath('helloworld', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)

        def run_once():
            dbg = DebuggerController(bv)
            dbg.cmd_line = 'foobar'
            self.assertTrue(dbg.launch())

            # continue execution to the entry point, and check the stop reason
            reason = dbg.go()
            self.assertEqual(reason, DebugStopReason.Breakpoint)
            reason = dbg.step_into()
            self.assertEqual(reason, DebugStopReason.SingleStep)
            reason = dbg.step_into()
            self.assertEqual(reason, DebugStopReason.SingleStep)
            reason = dbg.step_into()
            self.assertEqual(reason, DebugStopReason.SingleStep)
            # go until executing done
            reason = dbg.go()
            self.assertEqual(reason, DebugStopReason.ProcessExited)

            dbg.destroy()

        # Do the same thing for 10 times
        n = 10
        for i in range(n):
            with self.subTest(i=i):
                run_once()

    def test_return_code(self):
        # return code tests
        fpath = testbin_to_fpath('exitcode', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)

        # some systems return byte, or low byte of 32-bit code and others return 32-bit code
        testvals = [('-11', [245, 4294967285]),
                    ('-1', [4294967295, 255]),
                    ('-3', [4294967293, 253]),
                    ('0', [0]),
                    ('3', [3]),
                    ('7', [7]),
                    ('123', [123])]

        for case in testvals:
            with self.subTest(case):
                arg, expected = case
                dbg = DebuggerController(bv)
                dbg.cmd_line = arg

                self.assertTrue(dbg.launch())
                dbg.go()
                reason = dbg.go()
                self.assertEqual(reason, DebugStopReason.ProcessExited)
                exit_code = dbg.exit_code
                self.assertIn(exit_code, expected)

    def test_exception(self):
        fpath = testbin_to_fpath('do_exception', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)

        with self.subTest('segfault'):
            dbg.cmd_line = 'segfault'
            self.assertTrue(dbg.launch())
            dbg.go()
            reason = dbg.go()
            self.assertEqual(reason, DebugStopReason.AccessViolation)
            dbg.quit()

        # This would not work until we fix the test binary
        # with self.subTest('illegalinstr'):
        #     dbg.cmd_line = 'illegalinstr'
        #     self.assertTrue(dbg.launch())
        #     dbg.go()
        #     reason = dbg.go()
        #     if platform.system() in ['Windows', 'Linux']:
        #         expected = DebugStopReason.AccessViolation
        #     else:
        #         expected = DebugStopReason.IllegalInstruction
        #
        #     self.assertEqual(reason, expected)
        #     dbg.quit()

        if not self.arch == 'arm64':
            with self.subTest('divzero'):
                dbg.cmd_line = 'divzero'
                self.assertTrue(dbg.launch())
                dbg.go()
                reason = dbg.go()
                self.assertEqual(reason, DebugStopReason.Calculation)
                dbg.quit()

    def test_step_into(self):
        fpath = testbin_to_fpath('helloworld', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        dbg.cmd_line = 'foobar'
        self.assertTrue(dbg.launch())
        reason = dbg.go()
        self.assertEqual(reason, DebugStopReason.Breakpoint)
        reason = dbg.step_into()
        self.assertEqual(reason, DebugStopReason.SingleStep)
        reason = dbg.step_into()
        self.assertEqual(reason, DebugStopReason.SingleStep)
        reason = dbg.go()
        self.assertEqual(reason, DebugStopReason.ProcessExited)

    def test_breakpoint(self):
        fpath = testbin_to_fpath('helloworld', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        self.assertTrue(dbg.launch())
        # TODO: right now we are not returning whether the operation succeeds, so we cannot use assertTrue/assertFalse
        # breakpoint set/clear should fail at 0
        self.assertIsNone(dbg.add_breakpoint(0))
        self.assertIsNone(dbg.delete_breakpoint(0))

        # breakpoint set/clear should succeed at entrypoint
        entry = dbg.live_view.entry_point
        self.assertIsNone(dbg.delete_breakpoint(entry))
        self.assertIsNone(dbg.add_breakpoint(entry))

        reason = dbg.go()
        self.assertEqual(reason, DebugStopReason.Breakpoint)

        self.assertEqual(dbg.ip, entry)
        dbg.quit()

    def test_register_read_write(self):
        fpath = testbin_to_fpath('helloworld', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        self.assertTrue(dbg.launch())
        dbg.go()

        arch_name = bv.arch.name
        if arch_name == 'x86':
            (xax, xbx) = ('eax', 'ebx')
            (testval_a, testval_b) = (0xDEADBEEF, 0xCAFEBABE)
        elif arch_name == 'x86_64':
            (xax, xbx) = ('rax', 'rbx')
            (testval_a, testval_b) = (0xAAAAAAAADEADBEEF, 0xBBBBBBBBCAFEBABE)
        else:
            (xax, xbx) = ('x0', 'x1')
            (testval_a, testval_b) = (0xAAAAAAAADEADBEEF, 0xBBBBBBBBCAFEBABE)

        rax = dbg.get_reg_value(xax)
        rbx = dbg.get_reg_value(xbx)

        dbg.set_reg_value(xax, testval_a)
        self.assertEqual(dbg.get_reg_value(xax), testval_a)
        dbg.set_reg_value(xbx, testval_b)
        self.assertEqual(dbg.get_reg_value(xbx), testval_b)

        dbg.set_reg_value(xax, rax)
        self.assertEqual(dbg.get_reg_value(xax), rax)
        dbg.set_reg_value(xbx, rbx)
        self.assertEqual(dbg.get_reg_value(xbx), rbx)

        dbg.quit()

    def test_memory_read_write(self):
        fpath = testbin_to_fpath('helloworld', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        self.assertTrue(dbg.launch())
        dbg.go()

        addr = dbg.ip
        data = dbg.read_memory(addr, 256)
        self.assertFalse(dbg.write_memory(0, b'heheHAHAherherHARHAR'), False)
        data2 = b'\xAA' * 256
        dbg.write_memory(addr, data2)

        self.assertEqual(len(dbg.read_memory(0, 256)), 0)
        self.assertEqual(dbg.read_memory(addr, 256), data2)
        dbg.write_memory(addr, data)
        self.assertEqual(dbg.read_memory(addr, 256), data)

        dbg.quit()

    def test_thread(self):
        fpath = testbin_to_fpath('helloworld_thread', self.arch)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        self.assertTrue(dbg.launch())
        dbg.go()

        # We must resume the target on a different thread and pause it from the current thread.
        # I do not know why, but if I do it in the opposite way, python crashes when I launch the next target.
        # This is not observed when I use the debugger from within BN, so I have no easy means of debugging it
        t = threading.Thread(target=lambda dbg: dbg.go(), args=(dbg,))
        t.start()

        time.sleep(1)
        dbg.pause()

        # print('switching to bad thread')
        # self.assertFalse(dbg.thread_select(999))

        if platform.system() == 'Windows':
            # main thread at WaitForMultipleObjects() + 4 created threads + debugger thread
            nthreads_expected = 9
        else:
            # main thread at pthread_join() + 4 created threads
            nthreads_expected = 5

        threads = dbg.threads
        self.assertEqual(len(threads), nthreads_expected)

        tid_active = dbg.active_thread
        addrs = []
        for thread in threads:
            addrs.append(thread.rip)

        t = threading.Thread(target=lambda dbg: dbg.go(), args=(dbg,))
        t.start()

        time.sleep(1)
        dbg.pause()

        threads = dbg.threads
        self.assertEqual(len(threads), nthreads_expected)
        # ensure the eip/rip are in different locations (that the continue actually continued)
        addrs2 = []
        for thread in threads:
            addr = thread.rip
            addrs2.append(addr)

        if not is_wow64(fpath):
            self.assertNotEqual(addrs, addrs2)

        dbg.quit()

    def test_assembly_code(self):
        if self.arch == 'x86_64':
            fpath = testbin_to_fpath('asmtest', 'x86_64')
            bv = BinaryViewType.get_view_of_file(fpath)
            dbg = DebuggerController(bv)
            self.assertTrue(dbg.launch())
            entry = dbg.live_view.entry_point
            ip = dbg.ip
            has_loader = ip != entry

            # a few steps in the loader
            if has_loader:
                reason = dbg.step_into()
                self.assertEqual(reason, DebugStopReason.SingleStep)
                reason = dbg.step_into()
                self.assertEqual(reason, DebugStopReason.SingleStep)
                # go to entry
                dbg.go()
                self.assertEqual(dbg.ip, entry)

            # TODO: we can use BN to disassemble the binary and find out how long is the instruction
            # step into nop
            dbg.step_into()
            self.assertEqual(dbg.ip, entry+1)
            # step into call, return
            dbg.step_into()
            dbg.step_into()
            # back
            self.assertEqual(dbg.ip, entry+6)
            dbg.step_into()
            # step into call, return
            dbg.step_into()
            dbg.step_into()
            # back
            self.assertEqual(dbg.ip, entry+12)

            reason = dbg.go()
            self.assertEqual(reason, DebugStopReason.ProcessExited)

    def test_attach(self):
        pid = None
        if platform.system() == 'Windows':
            fpath = testbin_to_fpath('helloworld_loop', self.arch)
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_CONSOLE = 0x00000010
            cmds = [fpath]
            pid = subprocess.Popen(cmds, creationflags=CREATE_NEW_CONSOLE).pid
        elif platform.system() in ['Darwin', 'linux']:
            fpath = testbin_to_fpath('helloworld_loop', self.arch)
            cmds = [fpath]
            pid = subprocess.Popen(cmds).pid
        else:
            print('attaching test not yet implemented on %s' % platform.system())

        self.assertIsNotNone(pid)
        bv = BinaryViewType.get_view_of_file(fpath)
        dbg = DebuggerController(bv)
        self.assertTrue(dbg.attach(pid))
        for i in range(4):
            t = threading.Thread(target=lambda dbg: dbg.go(), args=(dbg,))
            t.start()

            time.sleep(2)
            dbg.pause()

            regs = dbg.regs
            self.assertTrue(len(regs) > 0)

        dbg.quit()


class DebuggerArm64Test(DebuggerAPI):
    def setUp(self) -> None:
        self.arch = 'arm64'


class Debuggerx64Test(DebuggerAPI):
    def setUp(self) -> None:
        self.arch = 'x86_64'


class Debuggerx86Test(DebuggerAPI):
    def setUp(self) -> None:
        self.arch = 'x86'


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    if platform.system() == 'Darwin':
        if platform.machine() == 'arm64':
            tests = loader.loadTestsFromTestCase(DebuggerArm64Test)
            suite.addTests(tests)
        tests = loader.loadTestsFromTestCase(Debuggerx64Test)
        suite.addTests(tests)
    elif platform.system() in ['Linux', 'Windows']:
        tests = loader.loadTestsFromTestCase(Debuggerx64Test)
        suite.addTests(tests)
        tests = loader.loadTestsFromTestCase(Debuggerx86Test)
        suite.addTests(tests)

    return suite
