"use client";

import React, { useState, useEffect, useRef } from "react";
import { ChevronDown } from "lucide-react";

export default function Combobox({
  id,
  options,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  id: string;
  options: string[];
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [justFocused, setJustFocused] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSearch(value);
  }, [value]);

  const filteredOptions = options.filter((opt) =>
    opt.toLowerCase().includes(search.toLowerCase())
  );

  useEffect(() => {
    setActiveIndex(-1);
  }, [search, isOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearch(value);
        setJustFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [value]);

  function onKeyDown(e: React.KeyboardEvent) {
    if (!isOpen) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        setIsOpen(true);
        e.preventDefault();
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => Math.min(prev + 1, filteredOptions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < filteredOptions.length) {
        const opt = filteredOptions[activeIndex];
        onChange(opt);
        setSearch(opt);
        setIsOpen(false);
        setJustFocused(false);
      }
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setSearch(value);
      setJustFocused(false);
    }
  }

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500">
        <input
          id={id}
          type="text"
          className="bg-transparent text-sm text-white w-full outline-none"
          placeholder={placeholder}
          value={search}
          disabled={disabled}
          role="combobox"
          aria-expanded={isOpen}
          aria-autocomplete="list"
          aria-controls={`${id}-listbox`}
          aria-activedescendant={activeIndex >= 0 ? `${id}-opt-${activeIndex}` : undefined}
          onKeyDown={onKeyDown}
          onChange={(e) => {
            const val = e.target.value;
            if (justFocused && value !== "") {
              setJustFocused(false);
              if (val === "") {
                setSearch("");
              } else if (val.length < value.length && (value.startsWith(val) || value.endsWith(val))) {
                setSearch("");
              } else {
                const typed = val.replace(value, "");
                setSearch(typed || val);
              }
              return;
            }
            setSearch(val);
            setIsOpen(true);
          }}
          onFocus={(e) => {
            setIsOpen(true);
            setJustFocused(true);
            const target = e.target;
            setTimeout(() => {
              target.select();
            }, 50);
          }}
        />
        <button
          type="button"
          tabIndex={-1}
          className="text-zinc-500 hover:text-zinc-350 outline-none"
          onClick={() => setIsOpen(!isOpen)}
          disabled={disabled}
        >
          <ChevronDown className={`h-4 w-4 transform transition-transform ${isOpen ? "rotate-185" : ""}`} />
        </button>
      </div>
      {isOpen && (
        <ul
          id={`${id}-listbox`}
          role="listbox"
          className="absolute z-50 w-full mt-2 max-h-60 overflow-y-auto bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl divide-y divide-zinc-800/40"
        >
          {filteredOptions.length > 0 ? (
            filteredOptions.map((opt, idx) => (
              <li
                key={opt}
                id={`${id}-opt-${idx}`}
                role="option"
                aria-selected={opt === value}
                className={`px-4 py-2.5 text-sm cursor-pointer transition-colors ${
                  idx === activeIndex
                    ? "bg-indigo-600 text-white"
                    : opt === value
                    ? "bg-indigo-600/30 text-indigo-400 font-semibold"
                    : "text-zinc-300 hover:bg-zinc-800"
                }`}
                onClick={() => {
                  onChange(opt);
                  setSearch(opt);
                  setIsOpen(false);
                  setJustFocused(false);
                }}
              >
                {opt}
              </li>
            ))
          ) : (
            <li className="px-4 py-3 text-sm text-zinc-500 italic">No matches found</li>
          )}
        </ul>
      )}
    </div>
  );
}
