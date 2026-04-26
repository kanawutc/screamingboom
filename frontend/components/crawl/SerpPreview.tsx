"use client";

import React, { useState } from "react";

interface SerpPreviewProps {
    url: string;
    title: string | null;
    titlePixelWidth: number | null;
    metaDescription: string | null;
    metaDescLength: number | null;
}

const MAX_TITLE_PX = 580;
const MAX_DESC_CHARS = 160;

function urlBreadcrumb(url: string): string {
    try {
        const u = new URL(url);
        const parts = u.pathname.split("/").filter(Boolean);
        if (parts.length === 0) return u.hostname;
        return `${u.hostname} › ${parts.join(" › ")}`;
    } catch {
        return url;
    }
}

export default function SerpPreview({
    url,
    title,
    titlePixelWidth,
    metaDescription,
    metaDescLength,
}: SerpPreviewProps) {
    const [editTitle, setEditTitle] = useState<string | null>(null);
    const [editDesc, setEditDesc] = useState<string | null>(null);

    const displayTitle = editTitle ?? title ?? "No title";
    const displayDesc = editDesc ?? metaDescription ?? "";

    const isTitleTruncated = titlePixelWidth != null && titlePixelWidth > MAX_TITLE_PX;
    const isDescTruncated = (metaDescLength ?? displayDesc.length) > MAX_DESC_CHARS;

    return (
        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-1">
            <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
                SERP Preview
            </p>

            {/* Title */}
            <div className="group relative">
                {editTitle !== null ? (
                    <input
                        className="text-[20px] leading-[26px] text-[#1a0dab] w-full bg-transparent border-b border-dashed border-blue-300 outline-none font-normal"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => setEditTitle(null)}
                        autoFocus
                    />
                ) : (
                    <h3
                        className="text-[20px] leading-[26px] text-[#1a0dab] hover:underline cursor-pointer font-normal overflow-hidden whitespace-nowrap text-ellipsis"
                        style={{ maxWidth: "600px" }}
                        onClick={() => setEditTitle(displayTitle)}
                        title="Click to edit title for what-if testing"
                    >
                        {displayTitle}
                    </h3>
                )}
            </div>

            {/* URL breadcrumb */}
            <p
                className="text-[14px] text-[#006621] truncate"
                style={{ maxWidth: "600px" }}
            >
                {urlBreadcrumb(url)}
            </p>

            {/* Description */}
            <div className="group relative">
                {editDesc !== null ? (
                    <textarea
                        className="text-[14px] leading-[22px] text-[#4d5156] w-full bg-transparent border-b border-dashed border-gray-300 outline-none resize-none"
                        value={editDesc}
                        onChange={(e) => setEditDesc(e.target.value)}
                        onBlur={() => setEditDesc(null)}
                        rows={3}
                        autoFocus
                    />
                ) : (
                    <p
                        className="text-[14px] leading-[22px] text-[#4d5156] cursor-pointer"
                        style={{ maxWidth: "600px" }}
                        onClick={() => setEditDesc(displayDesc)}
                        title="Click to edit description for what-if testing"
                    >
                        {displayDesc
                            ? displayDesc.length > MAX_DESC_CHARS
                                ? displayDesc.slice(0, MAX_DESC_CHARS) + "..."
                                : displayDesc
                            : "No meta description"}
                    </p>
                )}
            </div>

            {/* Warnings */}
            {(isTitleTruncated || isDescTruncated) && (
                <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t border-gray-100">
                    {isTitleTruncated && (
                        <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            ⚠️ Title truncated ({titlePixelWidth}px / {MAX_TITLE_PX}px max)
                        </span>
                    )}
                    {isDescTruncated && (
                        <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                            ⚠️ Description truncated ({metaDescLength ?? displayDesc.length} / {MAX_DESC_CHARS} chars)
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}
