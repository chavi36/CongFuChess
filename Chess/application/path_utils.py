# # import os
# # from typing import Optional


# # def get_project_root(start_path: Optional[str] = None) -> str:
# #     """Return the repository root containing both application/ and kungfu_chess/."""
# #     base = os.path.abspath(start_path or os.getcwd())
# #     if os.path.isfile(base):
# #         base = os.path.dirname(base)

# #     while True:
# #         if os.path.isdir(os.path.join(base, "application")) and os.path.isdir(os.path.join(base, "kungfu_chess")):
# #             return base
# #         parent = os.path.dirname(base)
# #         if parent == base:
# #             return base
# #         base = parent


# # def resolve_project_path(*parts: str, start_path: Optional[str] = None) -> str:
# #     return os.path.abspath(os.path.join(get_project_root(start_path), *parts))


# # def resolve_board_image(start_path: Optional[str] = None) -> str:
# #     root = get_project_root(start_path)
# #     candidates = [
# #         os.path.join(root, "board.png"),
# #         os.path.join(root, "kungfu_chess", "board.png"),
# #     ]
# #     for path in candidates:
# #         if os.path.isfile(path):
# #             return path
# #     return candidates[0]


# # def resolve_pieces_dir(start_path: Optional[str] = None) -> str:
# #     root = get_project_root(start_path)
# #     candidates = [
# #         os.path.join(root, "kungfu_chess", "animations"),
# #         os.path.join(root, "kungfu_chess", "anotations"),
# #     ]
# #     for path in candidates:
# #         if os.path.isdir(path):
# #             return path
# #     return candidates[0]


# import os
# from typing import Optional


# def get_project_root(start_path: Optional[str] = None) -> str:
#     """Return the repository root containing both application/ and client/."""
#     base = os.path.abspath(start_path or os.getcwd())
#     if os.path.isfile(base):
#         base = os.path.dirname(base)

#     while True:
#         # Now checks for 'application' and 'client' at the root
#         if os.path.isdir(os.path.join(base, "application")) and os.path.isdir(os.path.join(base, "client")):
#             return base
#         parent = os.path.dirname(base)
#         if parent == base:
#             return base
#         base = parent


# def resolve_project_path(*parts: str, start_path: Optional[str] = None) -> str:
#     return os.path.abspath(os.path.join(get_project_root(start_path), *parts))


# def resolve_board_image(start_path: Optional[str] = None) -> str:
#     root = get_project_root(start_path)
#     candidates = [
#         # Look inside the new client/kungfu_chess directory
#         os.path.join(root, "client", "kungfu_chess", "board.png"),
#         os.path.join(root, "board.png"),
#     ]
#     for path in candidates:
#         if os.path.isfile(path):
#             return path
#     return candidates[0]


# def resolve_pieces_dir(start_path: Optional[str] = None) -> str:
#     root = get_project_root(start_path)
#     candidates = [
#         # Look inside the new client/kungfu_chess directory
#         os.path.join(root, "client", "kungfu_chess", "animations"),
#         os.path.join(root, "client", "kungfu_chess", "anotations"),
#     ]
#     for path in candidates:
#         if os.path.isdir(path):
#             return path
#     return candidates[0]


import os
from typing import Optional


def get_project_root(start_path: Optional[str] = None) -> str:
    """Return the repository root containing both application/ and client/."""
    base = os.path.abspath(start_path or os.getcwd())
    if os.path.isfile(base):
        base = os.path.dirname(base)

    while True:
        if os.path.isdir(os.path.join(base, "application")) and os.path.isdir(os.path.join(base, "client")):
            return base
        parent = os.path.dirname(base)
        if parent == base:
            return base
        base = parent


def resolve_project_path(*parts: str, start_path: Optional[str] = None) -> str:
    return os.path.abspath(os.path.join(get_project_root(start_path), *parts))


def resolve_board_image(start_path: Optional[str] = None) -> str:
    root = get_project_root(start_path)
    candidates = [
        os.path.join(root, "Core", "board.png"),
        os.path.join(root, "board.png"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def resolve_pieces_dir(start_path: Optional[str] = None) -> str:
    root = get_project_root(start_path)
    candidates = [
        os.path.join(root, "Core", "animations"),
        os.path.join(root, "Core", "anotations"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]
