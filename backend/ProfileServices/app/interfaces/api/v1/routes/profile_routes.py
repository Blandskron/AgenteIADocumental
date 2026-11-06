import io
import uuid
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request

from app.application.use_cases.manage_profile import ManageProfile
from app.config.security import is_admin_user, require_authenticated_user, user_groups
from app.config.settings import Settings, get_settings
from app.interfaces.api.v1.dependencies import get_profile_use_case
from app.interfaces.api.v1.schemas.profile_schema import ProfileResponse, ProfileUpdateRequest, ProfileUploadResponse


router = APIRouter()


def _get_jwt_user_id(current_user: dict) -> str:
    user_id = current_user.get("user_id") or current_user.get("sub") or current_user.get("username")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token payload.",
        )
    return str(user_id)


def _get_jwt_permissions(current_user: dict) -> list[str]:
    return list(current_user.get("permissions") or current_user.get("user_permissions") or current_user.get("permisos") or [])


def _build_response(profile, current_user: dict) -> ProfileResponse:
    # If the profile belongs to the logged-in user, populate their groups and permissions
    # from their JWT. If not, these lists are empty (or not accessible).
    is_owner = str(profile.user_id) == _get_jwt_user_id(current_user)
    
    return ProfileResponse(
        profile_id=profile.profile_id,
        user_id=profile.user_id,
        email=profile.email,
        phone_number=profile.phone_number,
        profile_picture_url=profile.profile_picture_url,
        additional_info=profile.additional_info,
        groups=user_groups(current_user) if is_owner else [],
        permissions=_get_jwt_permissions(current_user) if is_owner else [],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get("/profile", response_model=ProfileResponse)
def get_own_profile(
    current_user: dict = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    user_id = _get_jwt_user_id(current_user)
    profile = use_case.get_profile(user_id)
    return _build_response(profile, current_user)


@router.put("/profile", response_model=ProfileResponse)
def update_own_profile(
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    user_id = _get_jwt_user_id(current_user)
    profile = use_case.update_profile(
        user_id=user_id,
        email=payload.email,
        phone_number=payload.phone_number,
        profile_picture_url=payload.profile_picture_url,
        additional_info=payload.additional_info,
    )
    return _build_response(profile, current_user)


@router.get("/profiles", response_model=list[ProfileResponse])
def list_profiles(
    current_user: dict = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required to list profiles.",
        )
    profiles = use_case.list_profiles()
    return [_build_response(p, current_user) for p in profiles]


@router.get("/profiles/{user_id}", response_model=ProfileResponse)
def get_profile_by_id(
    user_id: str,
    current_user: dict = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    caller_id = _get_jwt_user_id(current_user)
    if caller_id != user_id and not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this user's profile.",
        )
    profile = use_case.get_profile(user_id)
    return _build_response(profile, current_user)


@router.put("/profiles/{user_id}", response_model=ProfileResponse)
def update_profile_by_id(
    user_id: str,
    payload: ProfileUpdateRequest,
    current_user: dict = Depends(require_authenticated_user),
    use_case: ManageProfile = Depends(get_profile_use_case),
):
    caller_id = _get_jwt_user_id(current_user)
    if caller_id != user_id and not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to update this user's profile.",
        )
    profile = use_case.update_profile(
        user_id=user_id,
        email=payload.email,
        phone_number=payload.phone_number,
        profile_picture_url=payload.profile_picture_url,
        additional_info=payload.additional_info,
    )
    return _build_response(profile, current_user)


@router.post("/profile/upload", response_model=ProfileUploadResponse)
def upload_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_authenticated_user),
    settings: Settings = Depends(get_settings),
):
    # 1. Leer el contenido del archivo
    content = file.file.read()

    # 2. Verificar que es una imagen válida usando Pillow
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo proporcionado no es una imagen válida.",
        )

    # 3. Obtener el formato de la imagen
    img_format = img.format.lower() if img.format else "png"
    if img_format == "jpeg":
        img_format = "jpg"

    # 4. Generar nombre de archivo único
    filename = f"{uuid.uuid4().hex}.{img_format}"

    # 5. Guardar en el directorio físico
    file_path = settings.profile_uploads_dir / filename
    try:
        with file_path.open("wb") as f:
            f.write(content)
    except OSError:
        raise HTTPException(status_code=503, detail="Profile storage is unavailable.") from None

    # 6. Retornar URL dinámica
    base_url = str(request.base_url).rstrip("/")
    url = f"{base_url}/static/{filename}"
    return ProfileUploadResponse(url=url)

