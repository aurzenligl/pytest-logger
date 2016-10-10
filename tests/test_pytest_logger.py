def test_logdir_fixture(testdir):
    """Make sure that pytest accepts our fixture."""

    testdir.makepyfile("""
        def test_sth(logdir):
            assert str(logdir).endswith('/logs/test_logdir_fixture.py-test_sth')
    """)

    result = testdir.runpytest('-v')

    result.stdout.fnmatch_lines([
        '*::test_sth PASSED',
    ])

    assert result.ret == 0
