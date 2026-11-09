"""Fake ``unreal`` module recording calls. It is not Unreal and proves nothing about Unreal."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class Vector:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z


class Rotator:
    def __init__(self, roll: float = 0.0, pitch: float = 0.0, yaw: float = 0.0) -> None:
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw


class CameraActor:
    pass


class FakeActor:
    def __init__(self, cls: Any, label: str, location: Vector, rotation: Rotator) -> None:
        self.cls = cls
        self.label = label
        self.location = location
        self.rotation = rotation
        self.tags: list[str] = []

    def actor_has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def get_actor_label(self) -> str:
        return self.label

    def set_actor_label(self, label: str) -> None:
        self.label = label

    def get_actor_location(self) -> Vector:
        return self.location

    def get_actor_rotation(self) -> Rotator:
        return self.rotation


class FakeWorld:
    def __init__(self, path: str) -> None:
        self.path = path

    def get_path_name(self) -> str:
        return self.path


class _SystemLibrary:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner

    def execute_console_command(self, world: Any, command: str) -> None:
        self.owner.commands.append(command)
        if self.owner.auto_write:
            match = re.search(r'filename="([^"]+)"', command)
            if match:
                Path(match.group(1)).write_bytes(b"png")

    def get_console_variable_int_value(self, name: str) -> int:
        return self.owner.cvars.get(name, 2)


class _EditorLevelLibrary:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner

    def get_editor_world(self) -> FakeWorld:
        return FakeWorld(self.owner.map_path)

    def get_all_level_actors(self) -> list[FakeActor]:
        return list(self.owner.actors)

    def spawn_actor_from_class(self, cls: Any, location: Vector, rotation: Rotator) -> FakeActor:
        actor = FakeActor(cls, "", location, rotation)
        self.owner.actors.append(actor)
        return actor

    def get_level_viewport_camera_info(self) -> tuple[Any, ...]:
        pair = (self.owner.viewport_location, self.owner.viewport_rotation)
        return (True, *pair) if self.owner.viewport_with_status else pair

    def pilot_level_actor(self, actor: FakeActor) -> None:
        self.owner.piloted.append(actor)

    def get_game_world(self) -> FakeWorld | None:
        return self.owner.pie_world


class _GameplayStatics:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner

    def get_player_pawn(self, world: Any, index: int) -> FakeActor | None:
        assert world is self.owner.pie_world and index == 0
        return self.owner.pawn


class _Paths:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner

    def project_saved_dir(self) -> str:
        return str(self.owner.saved_dir) + "/"

    def convert_relative_path_to_full(self, path: str) -> str:
        return str(Path(path).resolve())


class FakeUnreal:
    def __init__(self, *, auto_write: bool = False) -> None:
        self.auto_write = auto_write
        self.commands: list[str] = []
        self.actors: list[FakeActor] = []
        self.piloted: list[FakeActor] = []
        self.cvars: dict[str, int] = {}
        self.map_path = "/Game/Maps/Arena.Arena"
        self.viewport_location = Vector(1234.5678, -42.125, 88.0)
        self.viewport_rotation = Rotator(roll=0.0, pitch=-10.5, yaw=135.25)
        self.viewport_with_status = True
        self.Vector = Vector
        self.Rotator = Rotator
        self.CameraActor = CameraActor
        self.SystemLibrary = _SystemLibrary(self)
        self.EditorLevelLibrary = _EditorLevelLibrary(self)
        self.saved_dir = "Saved"
        self.pie_world: FakeWorld | None = None
        self.pawn: FakeActor | None = None
        self.GameplayStatics = _GameplayStatics(self)
        self.Paths = _Paths(self)

    def add_camera(
        self,
        label: str,
        location: tuple[float, float, float],
        rotation: tuple[float, float, float],
    ) -> FakeActor:
        actor = FakeActor(
            CameraActor,
            label,
            Vector(*location),
            Rotator(roll=rotation[2], pitch=rotation[0], yaw=rotation[1]),
        )
        self.actors.append(actor)
        return actor


class UnrealEditorSubsystem:
    pass


class EditorActorSubsystem:
    pass


class LevelEditorSubsystem:
    pass


class _UnrealEditor58:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner
        self.legacy = _EditorLevelLibrary(owner)

    def get_editor_world(self) -> FakeWorld:
        return self.legacy.get_editor_world()

    def get_level_viewport_camera_info(self) -> tuple[Any, ...]:
        return self.legacy.get_level_viewport_camera_info()

    def get_game_world(self) -> FakeWorld | None:
        return self.owner.pie_world


class _LevelEditor58:
    def __init__(self, owner: FakeUnreal) -> None:
        self.owner = owner
        self.playing: bool | None = None

    def pilot_level_actor(self, actor: FakeActor) -> None:
        self.owner.piloted.append(actor)

    def is_in_play_in_editor(self) -> bool:
        if self.playing is not None:
            return self.playing
        return self.owner.pie_world is not None


class _UnrealEditor58WithSetter(_UnrealEditor58):
    def set_level_viewport_camera_info(self, location: Vector, rotation: Rotator) -> None:
        self.owner.viewport_location = location
        self.owner.viewport_rotation = rotation
        self.owner.viewport_moves.append((location, rotation))


class _Transaction:
    def __init__(self, owner: FakeUnreal, description: str) -> None:
        self.owner = owner
        self.description = description

    def __enter__(self) -> _Transaction:
        self.owner.transactions.append(self.description)
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeUnreal58(FakeUnreal):
    """UE 5.8 flavor: only the editor subsystems, no ``EditorLevelLibrary``."""

    def __init__(self, *, auto_write: bool = False, viewport_setter: bool = True) -> None:
        super().__init__(auto_write=auto_write)
        del self.EditorLevelLibrary
        self.UnrealEditorSubsystem = UnrealEditorSubsystem
        self.EditorActorSubsystem = EditorActorSubsystem
        self.LevelEditorSubsystem = LevelEditorSubsystem
        editor_cls = _UnrealEditor58WithSetter if viewport_setter else _UnrealEditor58
        legacy = _EditorLevelLibrary(self)
        self.subsystems: dict[Any, Any] = {
            UnrealEditorSubsystem: editor_cls(self),
            EditorActorSubsystem: legacy,
            LevelEditorSubsystem: _LevelEditor58(self),
        }
        self.viewport_moves: list[tuple[Vector, Rotator]] = []
        self.transactions: list[str] = []
        self.requested: list[Any] = []

    def get_editor_subsystem(self, cls: Any) -> Any:
        self.requested.append(cls)
        return self.subsystems.get(cls)

    def ScopedEditorTransaction(self, description: str) -> _Transaction:
        return _Transaction(self, description)


def start_pie(ue: FakeUnreal) -> FakeActor:
    """Simulate a running PIE session with a player pawn; returns the pawn."""
    ue.pie_world = FakeWorld("/Game/Maps/UEDPIE_0_Arena.Arena")
    ue.pawn = FakeActor(object, "Player", Vector(10.0, 20.0, 30.0), Rotator(0.0, -5.0, 90.0))
    return ue.pawn
