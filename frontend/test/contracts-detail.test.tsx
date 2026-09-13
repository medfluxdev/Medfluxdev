import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ContractDetailPage from "@/app/contracts/[contract-id]/page";
import type { ContractDetailResponse } from "@/lib/contract-detail-types";

const apiGetMock = vi.fn();
vi.mock("@/lib/api", () => ({
  apiGet: (...args: unknown[]) => apiGetMock(...args),
  contentUrl: (contractId: string, versionId: string) =>
    `http://test.local/content/${contractId}/${versionId}`,
}));

vi.mock("pdfjs-dist", () => {
  const pageStub = {
    getViewport: ({ scale }: { scale: number }) => ({ width: 400 * scale, height: 500 * scale }),
    render: () => ({ promise: Promise.resolve(), cancel: () => {} }),
  };
  const docStub = { numPages: 3, getPage: async () => pageStub, destroy: async () => {} };
  return { GlobalWorkerOptions: { workerSrc: "" }, getDocument: () => ({ promise: Promise.resolve(docStub) }) };
});

type NavState = { params: { "contract-id": string } };
const nav: NavState = { params: { "contract-id": "11111111-1111-1111-1111-111111111111" } };

vi.mock("next/navigation", () => ({
  useParams: () => nav.params,
  usePathname: () => `/contracts/${nav.params["contract-id"]}`,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

