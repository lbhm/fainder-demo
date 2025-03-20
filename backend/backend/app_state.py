import json
from dataclasses import dataclass

from loguru import logger

from backend.config import IndexingError, Metadata, Settings, configure_logging
from backend.croissant_store import CroissantStore, get_croissant_store
from backend.engine import Engine
from backend.indexing import generate_embedding_index, generate_fainder_indices, generate_metadata
from backend.indices import FainderIndex, HnswIndex, TantivyIndex
from backend.util import load_json


@dataclass
class InitializedComponents:
    """Container for initialized components."""

    settings: Settings
    metadata: Metadata
    croissant_store: CroissantStore
    tantivy_index: TantivyIndex
    fainder_index: FainderIndex
    hnsw_index: HnswIndex
    engine: Engine


class ApplicationState:
    """Class to manage the state of the backend application."""

    def __init__(self) -> None:
        self._components: InitializedComponents | None = None

    @property
    def croissant_store(self) -> CroissantStore:
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")
        return self._components.croissant_store

    @property
    def engine(self) -> Engine:
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")
        return self._components.engine

    @property
    def settings(self) -> Settings:
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")
        return self._components.settings

    def initialize(self) -> None:
        """Initialize all components of the application state."""
        try:
            logger.info("Initializing application state")
            settings = Settings()  # type: ignore

            # NOTE: Potentially add more modules here if they are not intercepted by loguru
            configure_logging(
                settings.log_level,
                modules=[
                    "fastapi",
                    "fastapi_cli",
                    "fastapi_cli.cli",
                    "fastapi_cli.discover",
                    "uvicorn",
                    "uvicorn.access",
                    "uvicorn.error",
                ],
            )

            try:
                # Try to load existing metadata and indices
                (
                    metadata,
                    croissant_store,
                    tantivy_index,
                    fainder_index,
                    hnsw_index,
                    engine,
                ) = self._load_indices(settings)
            except (FileNotFoundError, IndexingError) as e:
                logger.warning(f"Failed to load indices: {e}. Recreating...")
                (
                    metadata,
                    croissant_store,
                    tantivy_index,
                    fainder_index,
                    hnsw_index,
                    engine,
                ) = self._recreate_indices(settings)

            self._components = InitializedComponents(
                settings=settings,
                metadata=metadata,
                croissant_store=croissant_store,
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                engine=engine,
            )

        except Exception as e:
            logger.error(f"Failed to initialize application state: {e}")
            raise e

    def update_indices(self) -> None:
        settings = self.settings
        (
            metadata,
            croissant_store,
            tantivy_index,
            fainder_index,
            hnsw_index,
            engine,
        ) = self._recreate_indices(settings)
        self._components = InitializedComponents(
            settings=settings,
            metadata=metadata,
            croissant_store=croissant_store,
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            engine=engine,
        )

    def _load_indices(
        self, settings: Settings
    ) -> tuple[Metadata, CroissantStore, TantivyIndex, FainderIndex, HnswIndex, Engine]:
        logger.info("Loading metadata")
        metadata = Metadata(**load_json(settings.metadata_path))

        logger.info("Initializing Croissant store")
        croissant_store = get_croissant_store(
            store_type=settings.croissant_store_type,
            base_path=settings.croissant_path,
            doc_to_path=metadata.doc_to_path,
            dataset_slug=settings.dataset_slug,
            cache_size=settings.croissant_cache_size,
        )

        logger.info("Initializing Tantivy index")
        tantivy_index = TantivyIndex(settings.tantivy_path)

        logger.info("Initializing Fainder index")
        fainder_index = FainderIndex(
            rebinning_path=settings.rebinning_index_path,
            conversion_path=settings.conversion_index_path,
            histogram_path=settings.histogram_path,
        )

        logger.info("Initializing HNSW index")
        hnsw_index = HnswIndex(
            settings.hnsw_index_path,
            metadata,
            model=settings.embedding_model,
            use_embeddings=settings.use_embeddings,
            ef=settings.hnsw_ef,
        )

        logger.info("Initializing engine")
        engine = Engine(
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            metadata=metadata,
            cache_size=settings.query_cache_size,
        )
        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine

    def _recreate_indices(
        self, settings: Settings
    ) -> tuple[Metadata, CroissantStore, TantivyIndex, FainderIndex, HnswIndex, Engine]:
        """Recreate all indices from the croissant files."""
        # Generate metadata first
        hists, name_to_vector, _, tantivy_index = generate_metadata(
            croissant_path=settings.croissant_path,
            metadata_path=settings.metadata_path,
            tantivy_path=settings.tantivy_path,
        )

        # Load generated metadata
        with settings.metadata_path.open() as file:
            metadata = Metadata(**json.load(file))

        # Load Croissant documents
        croissant_store = get_croissant_store(
            store_type=settings.croissant_store_type,
            base_path=settings.croissant_path,
            doc_to_path=metadata.doc_to_path,
            dataset_slug=settings.dataset_slug,
            cache_size=settings.croissant_cache_size,
        )

        tantivy_index = TantivyIndex(settings.tantivy_path)

        # Generate indices
        generate_embedding_index(
            name_to_vector=name_to_vector,
            output_path=settings.embedding_path,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            ef_construction=settings.hnsw_ef_construction,
            n_bidirectional_links=settings.hnsw_n_bidirectional_links,
        )

        generate_fainder_indices(
            hists=hists,
            output_path=settings.fainder_path,
            n_clusters=settings.fainder_n_clusters,
            bin_budget=settings.fainder_bin_budget,
            alpha=settings.fainder_alpha,
            transform=settings.fainder_transform,
            algorithm=settings.fainder_cluster_algorithm,
        )

        # Initialize components with new indices
        fainder_index = FainderIndex(
            rebinning_path=settings.rebinning_index_path,
            conversion_path=settings.conversion_index_path,
            histogram_path=settings.histogram_path,
        )

        hnsw_index = HnswIndex(
            settings.hnsw_index_path,
            metadata,
            model=settings.embedding_model,
            use_embeddings=settings.use_embeddings,
            ef=settings.hnsw_ef,
        )

        engine = Engine(
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            metadata=metadata,
            cache_size=settings.query_cache_size,
        )

        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine
