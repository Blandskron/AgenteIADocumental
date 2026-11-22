#!/usr/bin/env python3
"""
Generates the narrated end-to-end showcase video for Blandskron Documental:
- Output video: docs/assets/video/blandskron-documental-demo.mp4
  (Single-pass Constant Frame Rate 24fps H.264 Main@L4.0 yuv420p + Stereo 44.1kHz 192kbps AAC-LC +faststart)
- Output captions: docs/assets/video/blandskron-documental-demo.es.vtt (WebVTT Spanish captions)

Covers all 12 verified end-to-end workflows in both Light Mode and Dark Mode
with natural Spanish neural voice narration (edge-tts).
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path

import edge_tts
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SCREENSHOTS_DIR = ROOT / "docs" / "assets" / "screenshots"
VIDEO_DIR = ROOT / "docs" / "assets" / "video"
OUTPUT_MP4 = VIDEO_DIR / "blandskron-documental-demo.mp4"
OUTPUT_VTT = VIDEO_DIR / "blandskron-documental-demo.es.vtt"

VOICE = "es-MX-DaliaNeural"
RATE = "+4%"
WIDTH = 1280
HEIGHT = 800
SAMPLE_RATE = 44100
CHANNELS = 2

CHAPTERS = [
    {
        "num": 1,
        "title": "1. Acceso seguro y Bootstrap inicial (/login)",
        "subtitle": "Bootstrap transaccional de la primera cuenta administradora, JWT RS256 y Google OIDC opcional.",
        "light_img": "login.webp",
        "dark_img": "login-dark.webp",
        "narration": (
            "Bienvenido al recorrido completo de Blandskron Documental. "
            "En el primer arranque, el sistema ofrece configuración inicial transaccional "
            "para crear la primera cuenta administradora sin editar archivos punto env, "
            "con autenticación J W T R S 256, diseño Floating Glass en modo claro y oscuro, "
            "y soporte opcional para Google O I D C."
        ),
    },
    {
        "num": 2,
        "title": "2. Biblioteca documental, búsqueda híbrida e ingesta E5 (/documents)",
        "subtitle": "Embeddings locales multilingual-e5-small en CPU, OCR, carpetas, favoritos y búsqueda FTS + trigram.",
        "light_img": "documents.webp",
        "dark_img": "documents-dark.webp",
        "narration": (
            "En la biblioteca documental puedes subir archivos P D F, Word, texto, Markdown o imágenes con O C R. "
            "La ingesta calcula embeddings locales de 384 dimensiones en C P U con el modelo multilingual E 5 small, "
            "organiza tus archivos en carpetas y favoritos, y permite buscar al instante combinando texto completo "
            "y similitud por trigramas."
        ),
    },
    {
        "num": 3,
        "title": "3. Aplicaciones: Google Drive OAuth PKCE y lotes Markdown/ZIP (/applications)",
        "subtitle": "Conexión OAuth PKCE S256 e importación masiva de bóvedas Obsidian/Logseq con protección anti zip-bomb.",
        "light_img": "applications-drive.webp",
        "dark_img": "applications-drive-dark.webp",
        "narration": (
            "Desde la sección de aplicaciones puedes conectar Google Drive mediante OAuth P K C E con verificación S 256, "
            "o importar colecciones completas de notas Markdown y archivos Z I P de Obsidian o Logseq, "
            "con deduplicación automática por hash S H A 256 y protección contra bombas Z I P."
        ),
    },
    {
        "num": 4,
        "title": "4. Chat documental RAG híbrido con citas verificables (/)",
        "subtitle": "Fusión HNSW pgvector + FTS con Reciprocal Rank Fusion (RRF), SafeMarkdown anti-XSS y exportación a PDF.",
        "light_img": "document-chat.webp",
        "dark_img": "document-chat-dark.webp",
        "narration": (
            "En el chat documental, el motor R A G híbrido fusiona la búsqueda vectorial H N S W en pgvector "
            "con búsqueda léxica mediante Reciprocal Rank Fusion. Cada respuesta se renderiza en Markdown seguro anti X S S, "
            "anclando cada afirmación a su fuente original numerada y permitiendo exportar la conversación verificada a P D F."
        ),
    },
    {
        "num": 5,
        "title": "5. Agente IA multi-paso y Code Mode en Sandbox Deno (/)",
        "subtitle": "Orquestación con checkpoints en agents.*, ejecución aislada Deno --deny-all, cuotas y aprobación humana.",
        "light_img": "agent-orchestrator.webp",
        "dark_img": "agent-orchestrator-dark.webp",
        "narration": (
            "El encabezado del chat integra tres modos en un solo flujo: Chat directo, Agente inteligente y Code Mode. "
            "El orquestador ejecuta planes multi-paso con plantillas de comparación de contratos, procesa cálculos deterministas "
            "de fechas y montos dentro de un sandbox Deno sin acceso a red ni secretos, controla la cuota de tokens por empresa "
            "y solicita aprobación humana explícita antes de persistir cambios."
        ),
    },
    {
        "num": 6,
        "title": "6. Knowledge Studio: Generador de artefactos P0 (/studio)",
        "subtitle": "Resúmenes ejecutivos, informes técnicos y tablas de evidencia con exportación Markdown y CSV segura.",
        "light_img": "knowledge-studio.webp",
        "dark_img": "knowledge-studio-dark.webp",
        "narration": (
            "En Knowledge Studio seleccionas documentos procesados reales y aplicas plantillas estructuradas "
            "para generar resúmenes ejecutivos, informes técnicos, tablas de evidencia o tareas propuestas. "
            "El editor detecta ediciones manuales para advertir sobre citas desvinculadas y permite descargar "
            "tanto en Markdown como en C S V seguro contra inyección de fórmulas."
        ),
    },
    {
        "num": 7,
        "title": "7. Knowledge Studio: Estudio Offline SM-2 y Quiz citado (/studio?artifact=art-001)",
        "subtitle": "Deep-linking hacia artefactos en studio.artifacts, tarjetas de repetición espaciada SM-2 y quiz con citas.",
        "light_img": "knowledge-studio-study.webp",
        "dark_img": "knowledge-studio-study-dark.webp",
        "narration": (
            "Al abrir la pestaña de artefactos o navegar mediante enlace directo desde el agente, "
            "puedes consultar las versiones guardadas en PostgreSQL, practicar retención documental cien por ciento offline "
            "en el navegador con tarjetas de repetición espaciada S M 2 sin consumir cuota de inteligencia artificial, "
            "y resolver cuestionarios verificados con retroalimentación y cita exacta."
        ),
    },
    {
        "num": 8,
        "title": "8. Configuración de IA Local: Ollama en CPU (/settings/ai)",
        "subtitle": "Ejecución local sin API key comercial ni envío a terceros, con catálogo CPU autorizado (Qwen 2.5, Gemma 2, Llama 3.2).",
        "light_img": "ai-settings.webp",
        "dark_img": "ai-settings-dark.webp",
        "narration": (
            "En Configuración de Inteligencia Artificial cada empresa elige su proveedor activo en caliente sin reiniciar contenedores. "
            "Con Ollama local puedes operar sin claves comerciales ni envío de datos a terceros, descargando modelos autorizados "
            "para C P U como Qwen 2 punto 5 o Gemma 2 según tu memoria R A M disponible."
        ),
    },
    {
        "num": 9,
        "title": "9. Configuración de IA en Nube: Groq cifrado con secrets1. (/settings/ai)",
        "subtitle": "Credenciales cifradas con Fernet autenticado, huella enmascarada, prueba en vivo y ajuste de parámetros.",
        "light_img": "ai-settings-groq.webp",
        "dark_img": "ai-settings-groq-dark.webp",
        "narration": (
            "Si prefieres la velocidad en la nube con Groq, la clave A P I se cifra en el servidor mediante Fernet autenticado "
            "con prefijo secrets 1 y llave maestra fuera de la base de datos. Desde aquí puedes probar la conexión en vivo, "
            "ajustar límite de tokens y temperatura, o revocar la credencial sin afectar los embeddings locales."
        ),
    },
    {
        "num": 10,
        "title": "10. Flujos de asignación, aprobación y firma documental (/documents/assignments)",
        "subtitle": "Distribución de documentos con vencimiento, notas de revisión, aceptación, rechazo y firma interna.",
        "light_img": "document-assignments.webp",
        "dark_img": "document-assignments-dark.webp",
        "narration": (
            "Para la gobernanza operativa, el módulo de asignaciones permite distribuir documentos críticos con fecha límite, "
            "notas de revisión y requisito de firma interna, registrando el estado pendiente, aceptado o rechazado de cada responsable."
        ),
    },
    {
        "num": 11,
        "title": "11. Administración multiempresa y control RBAC granular (/admin)",
        "subtitle": "Gestión de empresas (tenants), áreas jerárquicas, usuarios y grupos con 15 permisos granulares.",
        "light_img": "admin-panel.webp",
        "dark_img": "admin-panel-dark.webp",
        "narration": (
            "En el panel de administración gestionas múltiples empresas o tenants, áreas jerárquicas, "
            "aprovisionamiento de usuarios y grupos de seguridad con quince permisos granulares. "
            "Al cambiar de empresa activa, la interfaz remonta limpiamente el contexto para impedir cualquier mezcla de datos entre organizaciones."
        ),
    },
    {
        "num": 12,
        "title": "12. Auditoría de seguridad persistente (/admin/audit)",
        "subtitle": "Registro inmutable de cambios de IA, permisos y aprobaciones con filtrado reactivo AbortController.",
        "light_img": "audit-logs.webp",
        "dark_img": "audit-logs-dark.webp",
        "narration": (
            "Finalmente, el visor de auditoría de seguridad registra de forma inmutable cada cambio de proveedor de inteligencia artificial, "
            "cifrado de credenciales, aprobación de agentes y modificación de permisos, con filtrado reactivo y sin exponer jamás secretos ni tokens. "
            "Blandskron Documental está listo para ejecutarse en tu entorno con un solo comando de Docker Compose."
        ),
    },
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def render_annotated_slide(
    src_webp: Path,
    out_png: Path,
    chapter_num: int,
    total_chapters: int,
    theme_label: str,
    title: str,
    subtitle: str,
    progress_ratio: float,
) -> None:
    """Renders a 1280x800 frame from the high-DPI screenshot with a top badge, bottom caption bar and progress indicator."""
    with Image.open(src_webp) as raw:
        base = raw.convert("RGBA").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_badge = load_font(14, bold=True)
    font_title = load_font(18, bold=True)
    font_sub = load_font(14, bold=False)

    # Top-right chapter & theme pill
    badge_text = f"Paso {chapter_num}/{total_chapters} · {theme_label} · Audio en español"
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0] + 28
    bh = 32
    bx = WIDTH - bw - 20
    by = 16
    draw.rounded_rectangle(
        [bx, by, bx + bw, by + bh],
        radius=16,
        fill=(74, 20, 140, 236),
        outline=(216, 181, 255, 225),
        width=1,
    )
    draw.text((bx + 14, by + 6), badge_text, font=font_badge, fill=(255, 255, 255, 255))

    # Bottom caption bar (semi-transparent dark glass)
    bar_h = 72
    bar_y = HEIGHT - bar_h - 12
    draw.rounded_rectangle(
        [20, bar_y, WIDTH - 20, HEIGHT - 12],
        radius=14,
        fill=(18, 14, 26, 230),
        outline=(106, 39, 175, 210),
        width=1,
    )
    draw.text((38, bar_y + 10), title, font=font_title, fill=(248, 245, 251, 255))
    draw.text((38, bar_y + 36), subtitle, font=font_sub, fill=(216, 181, 255, 255))

    # Progress bar inside bottom of caption bar
    prog_x1 = 38
    prog_x2 = WIDTH - 38
    prog_y = bar_y + 62
    draw.rounded_rectangle([prog_x1, prog_y, prog_x2, prog_y + 4], radius=2, fill=(70, 57, 87, 200))
    fill_x2 = prog_x1 + int((prog_x2 - prog_x1) * max(0.02, min(1.0, progress_ratio)))
    draw.rounded_rectangle([prog_x1, prog_y, fill_x2, prog_y + 4], radius=2, fill=(216, 181, 255, 255))

    composed = Image.alpha_composite(base, overlay).convert("RGB")
    composed.save(out_png, "PNG")


def format_vtt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hrs:02d}:{mins:02d}:{secs:06.3f}"


async def synthesize_narration_to_wav(
    ffmpeg_exe: str,
    text: str,
    tmp_mp3: Path,
    out_wav: Path,
) -> float:
    """Synthesizes Spanish narration via edge-tts, converts to 44.1kHz Stereo PCM WAV with +0.45s tail silence, and returns exact duration in seconds."""
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(tmp_mp3))

    # Convert MP3 to normalized Stereo 44.1 kHz 16-bit PCM WAV with 0.45s tail padding
    subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(tmp_mp3),
            "-af",
            "volume=1.45,apad=pad_dur=0.45",
            "-ac",
            str(CHANNELS),
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(out_wav),
        ],
        check=True,
        capture_output=True,
    )

    with wave.open(str(out_wav), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def concatenate_wav_files(wav_paths: list[Path], master_wav: Path) -> float:
    """Concatenates all 12 PCM WAV files losslessly into a single continuous master WAV track."""
    total_frames = 0
    with wave.open(str(master_wav), "wb") as out_wf:
        out_wf.setnchannels(CHANNELS)
        out_wf.setsampwidth(2)
        out_wf.setframerate(SAMPLE_RATE)
        for p in wav_paths:
            with wave.open(str(p), "rb") as in_wf:
                data = in_wf.readframes(in_wf.getnframes())
                out_wf.writeframes(data)
                total_frames += in_wf.getnframes()
    return total_frames / float(SAMPLE_RATE)


async def build_video() -> None:
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    total = len(CHAPTERS)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        wav_files: list[Path] = []
        img_concat_lines: list[str] = []
        vtt_lines = ["WEBVTT", ""]
        current_time = 0.0
        last_png: Path | None = None

        for idx, chapter in enumerate(CHAPTERS):
            num = chapter["num"]
            tmp_mp3 = tmp_dir / f"ch_{num:02d}.mp3"
            out_wav = tmp_dir / f"ch_{num:02d}.wav"
            print(f"[{num}/{total}] Synthesizing Spanish voiceover for: {chapter['title']}...")
            seg_dur = await synthesize_narration_to_wav(
                ffmpeg_exe,
                chapter["narration"],
                tmp_mp3,
                out_wav,
            )
            wav_files.append(out_wav)

            half_dur = round(seg_dur / 2.0, 4)
            rem_dur = round(seg_dur - half_dur, 4)

            light_png = tmp_dir / f"ch_{num:02d}_light.png"
            dark_png = tmp_dir / f"ch_{num:02d}_dark.png"

            render_annotated_slide(
                SCREENSHOTS_DIR / chapter["light_img"],
                light_png,
                num,
                total,
                "Modo Claro",
                chapter["title"],
                chapter["subtitle"],
                progress_ratio=(idx + 0.5) / total,
            )
            render_annotated_slide(
                SCREENSHOTS_DIR / chapter["dark_img"],
                dark_png,
                num,
                total,
                "Modo Oscuro",
                chapter["title"],
                chapter["subtitle"],
                progress_ratio=(idx + 1.0) / total,
            )

            img_concat_lines.append(f"file '{light_png.as_posix()}'")
            img_concat_lines.append(f"duration {half_dur:.4f}")
            img_concat_lines.append(f"file '{dark_png.as_posix()}'")
            img_concat_lines.append(f"duration {rem_dur:.4f}")
            last_png = dark_png

            start_ts = format_vtt_time(current_time)
            end_ts = format_vtt_time(current_time + seg_dur)
            vtt_lines.append(f"{idx + 1}")
            vtt_lines.append(f"{start_ts} --> {end_ts}")
            vtt_lines.append(chapter["narration"])
            vtt_lines.append("")
            current_time += seg_dur

        if last_png is not None:
            img_concat_lines.append(f"file '{last_png.as_posix()}'")

        master_wav = tmp_dir / "master_narration.wav"
        total_audio_dur = concatenate_wav_files(wav_files, master_wav)
        print(f"Master stereo WAV track ready ({total_audio_dur:.2f}s). Encoding single-pass MP4...")

        img_list_txt = tmp_dir / "all_slides.txt"
        img_list_txt.write_text("\n".join(img_concat_lines), encoding="utf-8")

        # Single-pass CFR H.264 Main@L4.0 + Stereo AAC-LC 192kbps encode
        encode_cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(img_list_txt),
            "-i",
            str(master_wav),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            "fps=24,format=yuv420p",
            "-c:v",
            "libx264",
            "-profile:v",
            "main",
            "-level",
            "4.0",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(OUTPUT_MP4),
        ]
        subprocess.run(encode_cmd, check=True, capture_output=True)
        OUTPUT_VTT.write_text("\n".join(vtt_lines), encoding="utf-8")

    size_mb = OUTPUT_MP4.stat().st_size / (1024 * 1024)
    print(
        f"Done! Created {OUTPUT_MP4.relative_to(ROOT)} ({size_mb:.2f} MB, {total_audio_dur:.1f}s) "
        f"with continuous Stereo AAC audio and {OUTPUT_VTT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    asyncio.run(build_video())
