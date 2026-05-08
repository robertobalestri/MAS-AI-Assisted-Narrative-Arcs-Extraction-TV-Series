from typing import Callable, List

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.analysis_service import AnalysisService
from src.episode_reset_service import EpisodeResetService
from src.library_explorer_service import LibraryExplorerService
from src.series_ingestion_service import SeriesIngestionService
from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)
router = APIRouter(prefix="/api/library", tags=["library"])
ingestion_service = SeriesIngestionService()
analysis_service = AnalysisService()
explorer_service = LibraryExplorerService()
episode_reset_service = EpisodeResetService()


class SeriesCreateRequest(BaseModel):
    code: str
    display_name: str


class SeasonBatchCreateRequest(BaseModel):
    seasons: List[str]


class EpisodeBatchCreateRequest(BaseModel):
    episodes: List[str]


class UploadAssignmentRequest(BaseModel):
    upload_id: str
    season: str
    episode: str


def _handle_library_request(action: Callable[[], object], error_message: str, not_found: bool = False):
    try:
        return action()
    except ValueError as e:
        status_code = 404 if not_found else 400
        raise HTTPException(status_code=status_code, detail=str(e))
    except Exception as e:
        logger.error(f"{error_message}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/explorer")
async def get_library_explorer():
    return _handle_library_request(
        explorer_service.get_library_overview,
        "Error getting library explorer",
    )


@router.get("/explorer/{series}")
async def get_series_explorer(series: str):
    return _handle_library_request(
        lambda: explorer_service.get_series_overview(series),
        f"Error getting explorer detail for {series}",
        not_found=True,
    )


@router.post("/explorer/{series}/{season}/{episode}/generate-plot")
async def generate_episode_plot_from_srt(series: str, season: str, episode: str):
    return _handle_library_request(
        lambda: explorer_service.generate_plot_from_srt(series, season, episode),
        f"Error generating plot from SRT for {series} {season} {episode}",
    )


@router.post("/explorer/{series}/{season}/generate-plots")
async def generate_season_plots_from_srt(series: str, season: str):
    return _handle_library_request(
        lambda: explorer_service.generate_missing_plots_for_season(series, season),
        f"Error generating plots from SRT for {series} {season}",
    )


@router.post("/explorer/{series}/{season}/{episode}/analyze")
async def analyze_explorer_episode(series: str, season: str, episode: str):
    return _handle_library_request(
        lambda: explorer_service.analyze_episode(series, season, episode),
        f"Error analyzing episode {series} {season} {episode}",
    )


@router.post("/explorer/{series}/{season}/analyze-ready")
async def analyze_ready_explorer_episodes(series: str, season: str):
    return _handle_library_request(
        lambda: explorer_service.analyze_ready_episodes_for_season(series, season),
        f"Error analyzing ready episodes for {series} {season}",
    )


@router.post("/explorer/{series}/{season}/{episode}/reset")
async def reset_explorer_episode(series: str, season: str, episode: str):
    return _handle_library_request(
        lambda: {
            "reset": episode_reset_service.reset_episode(series, season, episode),
            "episode": explorer_service._build_episode_status(
                series.upper(),
                season.upper(),
                episode.upper(),
                explorer_service._load_progression_counts(),
            ),
        },
        f"Error resetting episode {series} {season} {episode}",
    )


@router.get("/series")
async def get_library_series():
    return _handle_library_request(
        ingestion_service.list_series,
        "Error getting library series",
    )


@router.post("/series")
async def create_library_series(request: SeriesCreateRequest):
    return _handle_library_request(
        lambda: ingestion_service.create_series(request.code, request.display_name),
        "Error creating series",
    )


@router.post("/series/{series}/seasons")
async def create_library_seasons(series: str, request: SeasonBatchCreateRequest):
    return _handle_library_request(
        lambda: ingestion_service.create_seasons(series, request.seasons),
        f"Error creating seasons for {series}",
    )


@router.post("/series/{series}/{season}/episodes")
async def create_library_episodes(series: str, season: str, request: EpisodeBatchCreateRequest):
    return _handle_library_request(
        lambda: ingestion_service.create_episodes(series, season, request.episodes),
        f"Error creating episodes for {series} {season}",
    )


@router.post("/series/{series}/uploads")
async def upload_library_plots(series: str, files: List[UploadFile] = File(...)):
    try:
        uploads = []
        for file in files:
            content = await file.read()
            uploads.append({"filename": file.filename or "upload.txt", "content": content.decode("utf-8")})
        return ingestion_service.register_uploads(series, uploads)
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded plot files must be UTF-8 text files")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading plots for {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/{season}/{episode}/upload")
async def upload_episode_source_file(series: str, season: str, episode: str, file: UploadFile = File(...)):
    try:
        content = await file.read()
        return ingestion_service.save_episode_source_file(
            series,
            season,
            episode,
            file.filename or "upload.txt",
            content.decode("utf-8"),
        )
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Uploaded files must be UTF-8 text files")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading episode source file for {series} {season} {episode}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/series/{series}/uploads/assign")
async def assign_library_upload(series: str, request: UploadAssignmentRequest):
    return _handle_library_request(
        lambda: ingestion_service.assign_upload(series, request.upload_id, request.season, request.episode),
        f"Error assigning upload for {series}",
    )


def _run_series_analysis(series: str) -> None:
    try:
        ingestion_service.set_analysis_state(series, "running")
        analysis_service.analyze_series(series)
        ingestion_service.set_analysis_state(series, "completed")
    except Exception as e:
        logger.error(f"Error analyzing series {series}: {str(e)}")
        ingestion_service.set_analysis_state(series, "failed", str(e))


@router.post("/series/{series}/analyze")
async def analyze_library_series(series: str, background_tasks: BackgroundTasks):
    try:
        status = ingestion_service.get_series_status(series)
        if status["expected_episode_count"] == 0:
            raise HTTPException(status_code=400, detail="Create at least one episode before analysis")
        if status["uploaded_episode_count"] == 0:
            raise HTTPException(status_code=400, detail="Upload at least one plot file before analysis")
        background_tasks.add_task(_run_series_analysis, series)
        ingestion_service.set_analysis_state(series, "running")
        return ingestion_service.get_series_status(series)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting analysis for {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/series/{series}/status")
async def get_library_series_status(series: str):
    try:
        return ingestion_service.get_series_status(series)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting status for {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
