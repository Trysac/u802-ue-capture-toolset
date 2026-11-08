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
