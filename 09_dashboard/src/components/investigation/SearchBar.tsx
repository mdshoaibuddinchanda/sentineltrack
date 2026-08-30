import React, { useState, useEffect } from "react";
import { Search, RotateCcw } from "lucide-react";

interface SearchBarProps {
  initialValue?: string;
  onSearch: (registration: string) => void;
  isLoading?: boolean;
}

export function SearchBar({ initialValue = "", onSearch, isLoading = false }: SearchBarProps) {
  const [query, setQuery] = useState(initialValue);

  useEffect(() => {
    setQuery(initialValue);
  }, [initialValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim().toUpperCase());
    }
  };

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value.toUpperCase())}
            placeholder="Enter vehicle license plate (e.g. GJ01AB1234)..."
            className="w-full bg-police-850 border border-police-700 focus:border-accent-blue rounded-lg pl-9 pr-4 py-2 text-sm font-mono text-slate-100 placeholder:text-slate-500 focus:outline-none shadow-inner"
          />
        </div>

        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className="px-4 py-2 bg-accent-blue hover:bg-blue-600 disabled:bg-police-750 disabled:text-slate-500 text-white rounded-lg text-xs font-bold font-mono tracking-wider transition-colors flex items-center gap-1.5 shadow-lg shadow-accent-blue/10"
        >
          {isLoading ? (
            <>
              <RotateCcw className="w-3.5 h-3.5 animate-spin" /> SCANNING
            </>
          ) : (
            <>TRACE ROUTE</>
          )}
        </button>
      </form>

    </div>
  );
}
