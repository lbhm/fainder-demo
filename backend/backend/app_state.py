from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from backend.config import IndexingError, Metadata, Settings, configure_logging
from backend.croissant_store import CroissantStore, get_croissant_store
from backend.engine import Engine
from backend.indexing import (
    generate_embedding_index,
    generate_fainder_indices,
    generate_metadata,
    save_histograms_parallel,
)
from backend.indices import FainderIndex, HnswIndex, TantivyIndex
from backend.utils import load_json


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

    def get_all_config_names(self, fainder_config_path: Path) -> list[str]:
        """Get all configuration names from the fainder configs.json file."""
        try:
            configs = load_json(fainder_config_path)
            return list(configs.keys())
        except FileNotFoundError:
            logger.warning("Configuration file {} not found", fainder_config_path)
            return []

    def initialize(self) -> None:
        """Initialize all components of the application state."""
        try:
            logger.info("Initializing application state")
            settings = Settings()  # type: ignore[call-arg]

            # NOTE: Potentially add more modules here if they are not intercepted by loguru
            configure_logging(settings.log_level)

            all_config_names = self.get_all_config_names(settings.fainder_config_path)

            try:
                # Try to load existing metadata and indices
                (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
                    self._load_indices(settings, all_config_names)
                )
            except (FileNotFoundError, IndexingError) as e:
                logger.warning("Failed to load indices: {}. Recreating...", e)
                (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
                    self._recreate_indices(settings, all_config_names)
                )

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
            logger.error("Failed to initialize application state: {}", e)
            raise

    def update_indices(self) -> None:
        """Update indices from the croissant files."""
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")

        settings = self.settings

        all_config_names = self.get_all_config_names(settings.fainder_config_path)

        logger.info("Updating indices with current configurations '{}'", all_config_names)

        (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
            self._recreate_indices(settings, all_config_names)
        )

        # Keep the current configuration
        self._components = InitializedComponents(
            settings=settings,
            metadata=metadata,
            croissant_store=croissant_store,
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            engine=engine,
        )

    def _load_config_from_json(
        self, config_name: str, settings: Settings
    ) -> dict[str, Any] | None:
        """Load configuration from configs.json file if it exists."""
        config_path = settings.fainder_path / "configs.json"
        try:
            configs = load_json(config_path)
        except FileNotFoundError:
            logger.warning("Configuration file {} not found", config_path)
            return None

        if config_name in configs:
            logger.info("Found configuration '{}' in configs.json", config_name)
            return configs[config_name]  # type: ignore[no-any-return]
        logger.warning("Configuration '{}' not found in configs.json", config_name)
        return None

    def _load_indices(
        self, settings: Settings, config_names: list[str]
    ) -> tuple[Metadata, CroissantStore, TantivyIndex, FainderIndex, HnswIndex, Engine]:
        logger.info("Loading metadata and indices with configurations '{}'", config_names)
        with settings.metadata_path.open("rb") as f:
            metadata = Metadata.model_validate_json(f.read())

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

        logger.info("Initializing Fainder index with configuration '{}'", config_names)

        rebinning_paths: dict[str, Path] = {}
        conversion_paths: dict[str, Path] = {}
        for config_name in config_names:
            # Use configuration-specific paths
            rebinning_path = settings.fainder_rebinning_path_for_config(config_name)
            conversion_path = settings.fainder_conversion_path_for_config(config_name)
            if not rebinning_path.exists() or not conversion_path.exists():
                raise FileNotFoundError(
                    f"Rebinning index for configuration '{config_name}' not found"
                )
            if not conversion_path.exists():
                raise FileNotFoundError(
                    f"Conversion index for configuration '{config_name}' not found"
                )
            rebinning_paths[config_name] = rebinning_path
            conversion_paths[config_name] = conversion_path

        fainder_index = FainderIndex(
            rebinning_paths=rebinning_paths,
            conversion_paths=conversion_paths,
            histogram_path=settings.histogram_path,
            num_workers=settings.fainder_num_workers,
            chunk_layout=settings.fainder_chunk_layout,
            num_chunks=settings.fainder_num_chunks,
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
            min_usability_score=settings.min_usability_score,
            rank_by_usability=settings.rank_by_usability,
            executor_type=settings.executor_type,
            max_workers=settings.max_workers,
        )
        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine

    def _recreate_indices(
        self, settings: Settings, config_names: list[str]
    ) -> tuple[Metadata, CroissantStore, TantivyIndex, FainderIndex, HnswIndex, Engine]:
        """Recreate all indices from the croissant files."""
        # Generate metadata first
        hists, name_to_vector, _, tantivy_index = generate_metadata(
            croissant_path=settings.croissant_path,
            metadata_path=settings.metadata_path,
            tantivy_path=settings.tantivy_path,
        )

        with settings.metadata_path.open("rb") as f:
            metadata = Metadata.model_validate_json(f.read())

        # Load Croissant documents
        croissant_store = get_croissant_store(
            store_type=settings.croissant_store_type,
            base_path=settings.croissant_path,
            doc_to_path=metadata.doc_to_path,
            dataset_slug=settings.dataset_slug,
            cache_size=settings.croissant_cache_size,
        )

        tantivy_index = TantivyIndex(settings.tantivy_path)

        # Generate embedding index
        generate_embedding_index(
            name_to_vector=name_to_vector,
            output_path=settings.embedding_path,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            ef_construction=settings.hnsw_ef_construction,
            n_bidirectional_links=settings.hnsw_n_bidirectional_links,
        )

        rebinning_paths: dict[str, Path] = {}
        conversion_paths: dict[str, Path] = {}

        for config_name in config_names:
            logger.info("Generating Fainder indices for configuration '{}'", config_name)
            # Load configuration from configs.json if available
            config_params = self._load_config_from_json(config_name, settings)

            if config_params:
                # Use parameters from configs.json
                logger.info("Using Fainder configuration from configs.json for '{}'", config_name)
                generate_fainder_indices(
                    hists=hists,
                    output_path=settings.fainder_path,
                    config_name=config_name,
                    n_clusters=config_params.get("n_clusters", settings.fainder_n_clusters),
                    bin_budget=config_params.get("bin_budget", settings.fainder_bin_budget),
                    alpha=config_params.get("alpha", settings.fainder_alpha),
                    transform=config_params.get("transform", settings.fainder_transform),
                    algorithm=config_params.get("algorithm", settings.fainder_cluster_algorithm),
                )
            else:
                # Fall back to settings values
                logger.info("Using Fainder configuration from settings for '{}'", config_name)
                generate_fainder_indices(
                    hists=hists,
                    output_path=settings.fainder_path,
                    config_name=config_name,
                    n_clusters=settings.fainder_n_clusters,
                    bin_budget=settings.fainder_bin_budget,
                    alpha=settings.fainder_alpha,
                    transform=settings.fainder_transform,
                    algorithm=settings.fainder_cluster_algorithm,
                )

            # Initialize components with new indices, using the configuration-specific paths
            rebinning_paths[config_name] = settings.fainder_rebinning_path_for_config(config_name)
            conversion_paths[config_name] = settings.fainder_conversion_path_for_config(
                config_name
            )

        save_histograms_parallel(
            hists,
            settings.histogram_path,
            n_chunks=settings.fainder_num_chunks,
            chunk_layout=settings.fainder_chunk_layout,
        )

        fainder_index = FainderIndex(
            rebinning_paths=rebinning_paths,
            conversion_paths=conversion_paths,
            histogram_path=settings.histogram_path,
            num_workers=settings.fainder_num_workers,
            num_chunks=settings.fainder_num_chunks,
            chunk_layout=settings.fainder_chunk_layout,
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
            min_usability_score=settings.min_usability_score,
            rank_by_usability=settings.rank_by_usability,
            executor_type=settings.executor_type,
            max_workers=settings.max_workers,
        )

        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine
