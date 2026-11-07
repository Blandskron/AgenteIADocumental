from threading import BoundedSemaphore


from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.use_cases.manage_profile import ManageProfile
from app.config.security import ProfileUser, require_authenticated_user
from app.interfaces.api.v1.dependencies import get_profile_use_case
from app.interfaces.api.v1.schemas.profile_schema import AvatarDeleteRequest, ProfileResponse, ProfileUpdateRequest
from app.domain.avatars import MAX_UPLOAD_BYTES, normalize_avatar


router = APIRouter()


def _build_response(profile, current_user: ProfileUser) -> ProfileResponse:
    return ProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        email=profile.email,
        phone_number=profile.phone_number,
        profile_picture_url=profile.profile_picture_url,
        additional_info=profile.additional_info,
        groups=current_user.groups,
        permissions=current_user.permissions,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        version=profile.version,
    )


@router.get("/profile", response_model=ProfileResponse)
def get_own_profile(
    current_user: ProfileUser = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    profile = use_case.get_profile()
    return _build_response(profile, current_user)


@router.put("/profile", response_model=ProfileResponse)
def update_own_profile(
    payload: ProfileUpdateRequest,
    current_user: ProfileUser = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    profile = use_case.update_profile(
        expected_version=payload.expected_version,
        changes=payload.model_dump(exclude_unset=True, exclude={"expected_version"}),
    )
    return _build_response(profile, current_user)



avatar_slots = BoundedSemaphore(2)


@router.post("/profile/upload", response_model=ProfileResponse, openapi_extra={
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["file", "expected_version"], "additionalProperties": False,
        "properties": {"file": {"type": "string", "format": "binary"},
                       "expected_version": {"type": "string", "pattern": "^(0|[1-9][0-9]{0,18})$"}},
    }}}},
})
async def upload_profile_picture(
    request: Request,
    current_user: ProfileUser = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    if not avatar_slots.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="Avatar processing is busy. Try again.")
    try:
        try:
            form = await request.form(max_files=1, max_fields=1, max_part_size=64)
        except OSError:
            raise HTTPException(status_code=503, detail="Avatar processing is unavailable.") from None
        except (StarletteHTTPException, ValueError):
            raise HTTPException(status_code=400, detail="Invalid avatar form.") from None
        try:
            if len(form.multi_items()) != 2 or set(form) != {"file", "expected_version"}:
                raise HTTPException(status_code=422, detail="File and expected_version are required.")
            file, expected = form["file"], form["expected_version"]
            if (not isinstance(file, UploadFile) or not file.filename or len(file.filename) > 256
                    or type(expected) is not str or not expected.isascii() or not expected.isdecimal()
                    or len(expected) > 19 or str(int(expected)) != expected or int(expected) > 2**63 - 2):
                raise HTTPException(status_code=422, detail="Invalid avatar form values.")
            try:
                content = await file.read(MAX_UPLOAD_BYTES + 1)
            except OSError:
                raise HTTPException(status_code=503, detail="Avatar processing is unavailable.") from None
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Avatar exceeds 5 MiB.")
            try:
                normalized = await run_in_threadpool(normalize_avatar, content)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid avatar image.") from None
            profile = await run_in_threadpool(use_case.replace_avatar, int(expected), normalized)
            return _build_response(profile, current_user)
        finally:
            await form.close()
    finally:
        avatar_slots.release()


@router.get("/profile/avatar", response_class=Response, responses={200: {"content": {"image/jpeg": {}}}})
def get_profile_avatar(
    version: int | None = Query(default=None, ge=1, le=2**63 - 1),
    current_user: ProfileUser = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    content = use_case.read_avatar(version)
    if content is None:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return Response(content=content, media_type="image/jpeg", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": 'inline; filename="avatar.jpg"',
    })


@router.delete("/profile/avatar", response_model=ProfileResponse)
def delete_profile_avatar(
    payload: AvatarDeleteRequest,
    current_user: ProfileUser = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    return _build_response(use_case.replace_avatar(payload.expected_version, None), current_user)
