from herdrill import sound


def test_ten_distinct_system_sound_styles_are_available():
    assert len(sound.SOUND_OPTIONS) == 10
    assert len({option.id for option in sound.SOUND_OPTIONS}) == 10
    assert {option.name for option in sound.SOUND_OPTIONS} == {
        "Tink",
        "Ping",
        "Pop",
        "Glass",
        "Hero",
        "Morse",
        "Submarine",
        "Funk",
        "Bottle",
        "Basso",
    }
    assert sound.sound_name("off") == "Muted"


class FakeProcess:
    def __init__(self):
        self.terminated = False
        self.waited = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.waited = True
        return 0


def test_player_is_nonblocking_and_replaces_the_previous_cue(monkeypatch):
    processes = []
    commands = []

    def popen(command, **kwargs):
        commands.append(command)
        process = FakeProcess()
        processes.append(process)
        return process

    monkeypatch.setattr(sound.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr(sound.subprocess, "Popen", popen)
    player = sound.SoundPlayer()

    assert player.available
    assert player.play("tink")
    assert commands[0][-1].endswith("Tink.aiff")
    assert player.play("submarine")
    assert processes[0].terminated and processes[0].waited
    assert commands[1][-1].endswith("Submarine.aiff")

    player.close()
    assert processes[1].terminated and processes[1].waited


def test_muted_or_unknown_sound_does_not_spawn_a_process(monkeypatch):
    monkeypatch.setattr(
        sound.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned")),
    )
    player = sound.SoundPlayer()
    assert not player.play("off")
    assert not player.play("unknown")
