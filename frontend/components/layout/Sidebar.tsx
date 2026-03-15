"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Bug, Settings, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Crawls", href: "/crawls", icon: Bug },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="hidden w-52 flex-shrink-0 flex-col bg-[#2b2d31] md:flex">
      <div className="flex h-11 items-center gap-2 border-b border-[#3a3d42] px-4">
        <div className="h-5 w-5 rounded bg-[#6cc04a] flex items-center justify-center">
          <Bug className="h-3 w-3 text-white" />
        </div>
        <span className="text-sm font-semibold text-white tracking-tight">SEO Spider</span>
      </div>

      <div className="px-3 pt-3 pb-2">
        <Link href="/crawls/new">
          <button className="w-full flex items-center justify-center gap-1.5 rounded bg-[#6cc04a] px-3 py-1.5 text-xs font-semibold text-white hover:bg-[#5aaa3c] transition-colors">
            <Plus className="h-3.5 w-3.5" />
            New Crawl
          </button>
        </Link>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 pt-1">
        {navigation.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                isActive
                  ? "bg-[#3a3d42] text-white"
                  : "text-[#a1a1aa] hover:bg-[#3a3d42] hover:text-white"
              )}
            >
              <item.icon className="h-3.5 w-3.5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[#3a3d42] px-4 py-2">
        <p className="text-[10px] text-[#71717a]">SEO Spider Clone v1.0</p>
      </div>
    </div>
  );
}
