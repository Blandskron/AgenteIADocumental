import { Search } from "lucide-react";

export function DocumentSearchBar({ isLoading, query, onQueryChange, onSearch }) {
  function handleSubmit(event) {
    event.preventDefault();
    onSearch();
  }

  return (
    <form className="document-search-bar" onSubmit={handleSubmit}>
      <div className="document-search-input">
        <Search size={18} />
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Buscar por nombre o contenido indexado"
        />
      </div>
      <button className="logout-button" disabled={isLoading}>
        {isLoading ? "Buscando..." : "Buscar"}
      </button>
    </form>
  );
}
