# Enterprise FastAPI + FastMCP Server (Core Scope-Based Architecture)

Kiến trúc chuẩn chỉnh kết hợp **FastAPI** (REST API & OpenAPI Docs) + **FastMCP** (Model Context Protocol Server) được tổng hợp từ các repository nổi bật trên GitHub:

1. **[`redhat-data-and-ai/template-mcp-server`](https://github.com/redhat-data-and-ai/template-mcp-server)**:
   - Pattern mount `mcp.http_app(path="/mcp")` vào FastAPI kèm **`combined_lifespan`** (`async with mcp_asgi_app.lifespan(app): yield`) để khởi tạo chuẩn xác session manager của Streamable HTTP transport.
2. **[`prowler-cloud/prowler`](https://github.com/prowler-cloud/prowler) (`prowler_mcp_server`)**:
   - Pattern `BaseTool` / `BaseScopedToolset` kế thừa hướng đối tượng kết hợp **Auto-Discovery (`pkgutil` + `__subclasses__()`)**.
   - Tự động suy luận MCP Safety Hints (`ToolAnnotations(readOnlyHint=..., destructiveHint=...)`) dựa theo tiền tố hàm (`get_`, `list_`, `delete_`, ...).
3. **[`koreainvestment/open-trading-api`](https://github.com/koreainvestment/open-trading-api) & [`ragieai/dynamic-fastmcp`](https://github.com/ragieai/dynamic-fastmcp)**:
   - Pattern Single-Tool Class (`BaseTool`) với hàm `execute()` có kiểm tra kiểu Pydantic `Field(...)`, tự động gắn logging, đo thời gian thực thi (execution timing) và gắn `scope` tag.

---

## Cấu trúc thư mục

```text
mcp-server-core/
├── main.py                      # Entrypoint chạy Uvicorn server (port 8000)
├── pyproject.toml               # Quản lý dependencies với uv
├── src/
│   ├── config.py                # Cấu hình tập trung qua Pydantic Settings (.env)
│   ├── mcp_server.py            # Khởi tạo FastMCP & Streamable HTTP ASGI app (/mcp)
│   ├── core/
│   │   ├── base_tool.py         # 2 Core Base Class: BaseTool & BaseScopedToolset
│   │   └── registry.py          # ToolRegistry: Auto-discovery & quản lý tool theo scope
│   ├── tools/                   # Nơi chứa các MCP Tool chia theo từng Scope
│   │   ├── system_scope.py      # Scope "system" (ví dụ kế thừa BaseTool)
│   │   ├── math_scope.py        # Scope "math"   (ví dụ kế thừa BaseTool)
│   │   └── user_scope.py        # Scope "users"  (ví dụ kế thừa BaseScopedToolset)
│   └── api/
│       ├── app.py               # FastAPI App + Combined Lifespan + Mount /mcp
│       └── routes.py            # REST API trả về MCP URL, danh sách MCP Tools & Scopes
└── tests/
    └── test_mcp_and_api.py      # Bộ test E2E cho cả FastAPI REST & FastMCP Client
```

---

## Cách thêm MCP Tool mới theo Scope (Chỉ cần kế thừa)

Khi muốn mở rộng thêm một scope mới (ví dụ `orders`, `payments`, `crm`), bạn chỉ cần tạo file mới trong `src/tools/` và chọn **1 trong 2 cách kế thừa** sau (không cần sửa code ở `mcp_server.py` hay `app.py` vì `ToolRegistry` tự động quét và đăng ký):

### Cách 1: Kế thừa `BaseTool` (1 Class = 1 Tool độc lập)

Phù hợp cho những tool phức tạp, có dependency/state riêng biệt:

```python
# src/tools/order_scope.py
from typing import Any
from pydantic import Field
from src.core.base_tool import BaseTool

class CheckOrderStatusTool(BaseTool):
    name = "orders_check_status"
    scope = "orders"
    description = "Kiểm tra trạng thái đơn hàng theo mã đơn."
    tags = {"ecommerce", "orders"}
    read_only = True

    async def execute(
        self,
        order_id: str = Field(description="Mã đơn hàng (VD: ORD-1001)"),
    ) -> dict[str, Any]:
        return {"order_id": order_id, "status": "processing"}
```

### Cách 2: Kế thừa `BaseScopedToolset` (1 Class = Nhiều Tool chung 1 Scope)

Phù hợp cho một module/domain có nhiều thao tác CRUD (`list_`, `get_`, `create_`, `delete_`). Mọi hàm `async def` public sẽ **tự động** trở thành MCP tool với tiền tố `<scope>_<method_name>` và tự động gắn `readOnlyHint` / `destructiveHint`:

```python
# src/tools/payment_scope.py
from typing import Any
from pydantic import Field
from src.core.base_tool import BaseScopedToolset

class PaymentScopedToolset(BaseScopedToolset):
    scope = "payments"
    prefix_with_scope = True  # get_invoice -> payments_get_invoice

    async def get_invoice(
        self,
        invoice_id: str = Field(description="Mã hóa đơn"),
    ) -> dict[str, Any]:
        """Lấy thông tin chi tiết hóa đơn (tự động có readOnlyHint=True)."""
        return {"invoice_id": invoice_id, "amount": 250000, "currency": "VND"}

    async def refund_invoice(
        self,
        invoice_id: str = Field(description="Mã hóa đơn cần hoàn tiền"),
    ) -> dict[str, Any]:
        """Hoàn tiền hóa đơn."""
        return {"invoice_id": invoice_id, "refunded": True}
```

---

## Chạy Server & Kiểm tra Output

### 1. Khởi chạy Server
```bash
uv run python main.py
```

### 2. Các URL quan trọng
- **MCP Server URL (Streamable HTTP)**: `http://localhost:8000/mcp`
- **Xem MCP URL + Toàn bộ List MCP Tools (JSON)**: `GET http://localhost:8000/api/v1/mcp/info`
- **Lọc danh sách MCP Tools theo Scope**: `GET http://localhost:8000/api/v1/mcp/tools?scope=users`
- **Xem danh sách các Scope**: `GET http://localhost:8000/api/v1/mcp/scopes`
- **Swagger UI (FastAPI Docs)**: `http://localhost:8000/docs`
