from dataclasses import dataclass
from typing import Any

from loguru import logger

from backend.config import IndexingError, Metadata, Settings, configure_logging
from backend.croissant_store import CroissantStore, get_croissant_store
from backend.engine import Engine
from backend.indexing import generate_embedding_index, generate_fainder_indices, generate_metadata
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
    current_fainder_config: str = "default"


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

    @property
    def current_fainder_config(self) -> str:
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")
        return self._components.current_fainder_config

    def initialize(self) -> None:
        """Initialize all components of the application state."""
        try:
            logger.info("Initializing application state")
            settings = Settings()  # type: ignore[call-arg]

            # NOTE: Potentially add more modules here if they are not intercepted by loguru
            configure_logging(settings.log_level)

            # Default to the "default" configuration
            current_config = settings.fainder_default

            try:
                # Try to load existing metadata and indices
                (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
                    self._load_indices(settings, current_config)
                )
            except (FileNotFoundError, IndexingError) as e:
                logger.warning("Failed to load indices: {}. Recreating...", e)
                (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
                    self._recreate_indices(settings, current_config)
                )

            self._components = InitializedComponents(
                settings=settings,
                metadata=metadata,
                croissant_store=croissant_store,
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                engine=engine,
                current_fainder_config=current_config,
            )
        except Exception as e:
            logger.error("Failed to initialize application state: {}", e)
            raise

    def update_indices(self) -> None:
        """Update indices from the croissant files, using the current config."""
        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")

        settings = self.settings
        current_config = self.current_fainder_config

        logger.info(f"Updating indices with current configuration '{current_config}'")

        (metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine) = (
            self._recreate_indices(settings, current_config)
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
            current_fainder_config=current_config,
        )

    def update_fainder_index(self, config_name: str) -> None:
        """Update the Fainder index with a specific configuration."""
        settings = self.settings
        logger.info(f"Updating Fainder index with configuration '{config_name}'")

        if self._components is None:
            raise RuntimeError("ApplicationState not initialized")

        # Get the paths for the specified configuration
        rebinning_path = settings.fainder_rebinning_path_for_config(config_name)
        conversion_path = settings.fainder_conversion_path_for_config(config_name)

        # Check if the configuration files exist
        if not rebinning_path.exists():
            raise FileNotFoundError(f"Rebinning index for configuration '{config_name}' not found")
        if not conversion_path.exists():
            raise FileNotFoundError(
                f"Conversion index for configuration '{config_name}' not found"
            )

        # Update the FainderIndex component
        self._components.fainder_index.update(
            rebinning_path=rebinning_path,
            conversion_path=conversion_path,
            histogram_path=settings.histogram_path,
        )

        # Update the engine with the new FainderIndex
        self._components.engine.update_indices(
            tantivy_index=self._components.tantivy_index,
            fainder_index=self._components.fainder_index,
            hnsw_index=self._components.hnsw_index,
            metadata=self._components.metadata,
        )

        # Update the current configuration
        self._components.current_fainder_config = config_name

        logger.info(f"Fainder index updated successfully with configuration '{config_name}'")

    def _load_config_from_json(
        self, config_name: str, settings: Settings
    ) -> dict[str, Any] | None:
        """Load configuration from configs.json file if it exists."""
        config_path = settings.fainder_path / "configs.json"
        try:
            configs = load_json(config_path)
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found")
            return None

        if config_name in configs:
            logger.info(f"Found configuration '{config_name}' in configs.json")
            return configs[config_name]  # type: ignore[no-any-return]
        logger.warning(f"Configuration '{config_name}' not found in configs.json")
        return None

    def _load_indices(
        self, settings: Settings, config_name: str = "default"
    ) -> tuple[Metadata, CroissantStore, TantivyIndex, FainderIndex, HnswIndex, Engine]:
        logger.info(f"Loading metadata and indices with configuration '{config_name}'")
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

        logger.info(f"Initializing Fainder index with configuration '{config_name}'")
        # Use configuration-specific paths
        rebinning_path = settings.fainder_rebinning_path_for_config(config_name)
        conversion_path = settings.fainder_conversion_path_for_config(config_name)

        # If the config doesn't exist, fall back to default values
        if not rebinning_path.exists() or not conversion_path.exists():
            logger.warning(f"Configuration '{config_name}' not found, falling back to default")
            rebinning_path = settings.rebinning_index_path
            conversion_path = settings.conversion_index_path

        fainder_index = FainderIndex(
            rebinning_path=rebinning_path,
            conversion_path=conversion_path,
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
            min_usability_score=settings.min_usability_score,
            rank_by_usability=settings.rank_by_usability,
            executor_type=settings.executor_type,
        )
        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine

    def _recreate_indices(
        self, settings: Settings, config_name: str = "default"
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

        # Load configuration from configs.json if available
        config_params: dict[str, Any] | None = self._load_config_from_json(config_name, settings)

        if config_params:
            # Use parameters from configs.json
            logger.info(f"Using Fainder configuration from configs.json for '{config_name}'")
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
            logger.info(f"Using Fainder configuration from settings for '{config_name}'")
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
        rebinning_path = settings.fainder_rebinning_path_for_config(config_name)
        conversion_path = settings.fainder_conversion_path_for_config(config_name)

        fainder_index = FainderIndex(
            rebinning_path=rebinning_path,
            conversion_path=conversion_path,
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
            min_usability_score=settings.min_usability_score,
            rank_by_usability=settings.rank_by_usability,
            executor_type=settings.executor_type,
        )

        return metadata, croissant_store, tantivy_index, fainder_index, hnsw_index, engine
