"use client";

import { useEffect, useRef, useState } from "react";
import {
  LoaderCircle,
  Network,
  Plus,
  Shuffle,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  assignProxyPool,
  clearProxyPoolAssignments,
  deleteProxyPool,
  fetchProxyPool,
  importProxyPool,
  type ProxyPoolItem,
} from "@/lib/api";

export function ProxyPoolCard() {
  const didLoadRef = useRef(false);
  const [items, setItems] = useState<ProxyPoolItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [importText, setImportText] = useState("");

  const load = async () => {
    setIsLoading(true);
    try {
      const data = await fetchProxyPool();
      setItems(data.items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "加载代理池失败");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (didLoadRef.current) return;
    didLoadRef.current = true;
    void load();
  }, []);

  const handleImport = async () => {
    const text = importText.trim();
    if (!text) {
      toast.error("请输入代理列表");
      return;
    }
    setIsImporting(true);
    try {
      const data = await importProxyPool(text);
      setItems(data.items);
      setImportText("");
      setShowImport(false);
      toast.success(`导入完成：新增 ${data.added ?? 0} 个，跳过 ${data.skipped ?? 0} 个`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导入失败");
    } finally {
      setIsImporting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const data = await deleteProxyPool([id]);
      setItems(data.items);
      toast.success("已删除");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除失败");
    }
  };

  const handleClearAll = async () => {
    try {
      const data = await deleteProxyPool([]);
      setItems(data.items);
      toast.success(`已清空代理池（删除 ${data.removed ?? 0} 个）`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "清空失败");
    }
  };

  const handleAssign = async () => {
    setIsAssigning(true);
    try {
      const data = await assignProxyPool();
      if (data.error) {
        toast.error(data.error);
      } else {
        toast.success(`已分配 ${data.assigned} 个账号（${data.total_proxies} 个代理轮转分配给 ${data.total_accounts} 个账号）`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "分配失败");
    } finally {
      setIsAssigning(false);
    }
  };

  const handleClearAssignments = async () => {
    setIsClearing(true);
    try {
      const data = await clearProxyPoolAssignments();
      toast.success(`已清除 ${data.cleared} 个账号的代理分配`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "清除失败");
    } finally {
      setIsClearing(false);
    }
  };

  return (
    <Card className="rounded-2xl border-white/80 bg-white/90 shadow-sm">
      <CardContent className="space-y-6 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-stone-100">
              <Network className="size-5 text-stone-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold tracking-tight">代理池</h2>
              <p className="text-sm text-stone-500">
                批量导入代理 IP 并自动分配给账号，每个账号使用独立出口。
              </p>
            </div>
          </div>
          <Badge variant={items.length > 0 ? "success" : "secondary"} className="w-fit rounded-md px-2.5 py-1">
            {items.length > 0 ? `${items.length} 个代理` : "未配置"}
          </Badge>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <LoaderCircle className="size-5 animate-spin text-stone-400" />
          </div>
        ) : (
          <>
            {/* Action buttons */}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
                onClick={() => setShowImport(!showImport)}
              >
                <Plus className="size-4" />
                导入代理
              </Button>
              <Button
                className="h-9 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
                onClick={() => void handleAssign()}
                disabled={isAssigning || items.length === 0}
              >
                {isAssigning ? <LoaderCircle className="size-4 animate-spin" /> : <Shuffle className="size-4" />}
                自动分配
              </Button>
              <Button
                variant="outline"
                className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
                onClick={() => void handleClearAssignments()}
                disabled={isClearing}
              >
                {isClearing ? <LoaderCircle className="size-4 animate-spin" /> : <XCircle className="size-4" />}
                清除分配
              </Button>
              {items.length > 0 && (
                <Button
                  variant="outline"
                  className="h-9 rounded-xl border-rose-200 bg-white px-4 text-rose-600 hover:bg-rose-50"
                  onClick={() => void handleClearAll()}
                >
                  <Trash2 className="size-4" />
                  清空代理池
                </Button>
              )}
            </div>

            {/* Import area */}
            {showImport && (
              <div className="space-y-3 rounded-xl border border-stone-200 bg-stone-50 p-4">
                <label className="text-sm font-medium text-stone-700">
                  批量导入（每行一个，格式：IP:端口:用户名:密码）
                </label>
                <Textarea
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                  placeholder={"1.2.3.4:8080:user1:pass1\n5.6.7.8:1080:user2:pass2"}
                  className="min-h-[120px] rounded-xl border-stone-200 bg-white font-mono text-xs"
                />
                <div className="flex gap-2">
                  <Button
                    className="h-9 rounded-xl bg-stone-950 px-4 text-white hover:bg-stone-800"
                    onClick={() => void handleImport()}
                    disabled={isImporting}
                  >
                    {isImporting ? <LoaderCircle className="size-4 animate-spin" /> : <Plus className="size-4" />}
                    确认导入
                  </Button>
                  <Button
                    variant="outline"
                    className="h-9 rounded-xl border-stone-200 bg-white px-4 text-stone-700"
                    onClick={() => { setShowImport(false); setImportText(""); }}
                  >
                    取消
                  </Button>
                </div>
              </div>
            )}

            {/* Proxy list */}
            {items.length > 0 && (
              <div className="space-y-2">
                <div className="text-sm font-medium text-stone-700">代理列表</div>
                <div className="max-h-[300px] overflow-y-auto rounded-xl border border-stone-200 bg-white">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 border-b border-stone-100 bg-stone-50">
                      <tr>
                        <th className="px-4 py-2 text-left font-medium text-stone-600">地址</th>
                        <th className="px-4 py-2 text-left font-medium text-stone-600">用户名</th>
                        <th className="px-4 py-2 text-right font-medium text-stone-600">操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id} className="border-b border-stone-50 last:border-0">
                          <td className="px-4 py-2 font-mono text-xs text-stone-800">
                            {item.host}:{item.port}
                          </td>
                          <td className="px-4 py-2 text-xs text-stone-500">
                            {item.username || "-"}
                          </td>
                          <td className="px-4 py-2 text-right">
                            <button
                              className="text-stone-400 hover:text-rose-500"
                              onClick={() => void handleDelete(item.id)}
                            >
                              <Trash2 className="size-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
