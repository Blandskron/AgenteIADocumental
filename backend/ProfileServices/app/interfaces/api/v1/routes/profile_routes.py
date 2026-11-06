import io
import uuid
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Request

from app.application.use_cases.manage_profile import ManageProfile
from app.config.security import ProfileUser, require_authenticated_user
from app.config.settings import Settings, get_settings
from app.interfaces.api.v1.dependencies import get_profile_use_case
from app.interfaces.api.v1.schemas.profile_schema import ProfileResponse, ProfileUpdateRequest, ProfileUploadResponse


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
    current_user: ProfileUser = Depends(require_authenticated_user),
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

