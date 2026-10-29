# Bingo Math — Spec

## Tổng quan

Bingo Math là web game cho các bé, chơi trong mạng LAN: mỗi số bingo (1–100) chỉ được khoanh sau khi một người chơi trả lời đúng một phép tính có kết quả bằng số đó. **Không có tài khoản hay đăng nhập**: ai cũng có thể tạo phòng, cấu hình luật, rồi mời mọi người quét QR vào chơi. Backend **FastAPI** (REST + WebSocket thuần), frontend **Vue 3**, chạy bằng **Docker Compose**.

Cách giao việc:

1. Dự án gồm 3 thư mục `docs/`, `backend/`, `frontend/` (xem *Cấu trúc dự án và phân công agent*).
2. **Agent điều phối (master)** chạy ở thư mục gốc và giao việc cho 2 agent con `backend-dev` và `frontend-dev` chạy song song. Mỗi agent con chỉ được sửa file trong thư mục của mình.
3. Mục *Hợp đồng REST API* và *Hợp đồng WebSocket* là nguồn sự thật chung. Chỉ master được sửa tài liệu trong `docs/`; agent con thấy cần đổi hợp đồng thì báo lại master, không tự ý đổi.
4. FE phát triển với **mock client** giả lập server, nên không phải chờ BE xong.
5. Khi cả hai xong, master chạy theo mục *Docker* rồi làm hết danh sách *Kiểm thử chung*.

## Cấu trúc dự án và phân công agent

```text
bingo-math/
  CLAUDE.md                    # hướng dẫn cho master agent
  README.md
  .claude/
    agents/backend-dev.md      # agent con BE
    agents/frontend-dev.md     # agent con FE
    hooks/only_in_dir.py       # chặn agent con ghi file ngoài thư mục của mình
  docs/
    spec.md                    # tài liệu này
    CHANGELOG.md               # các đính chính hợp đồng đã chốt
  backend/                     # FastAPI, có CLAUDE.md riêng
  frontend/                    # Vue 3, có CLAUDE.md riêng
  docker-compose.yml · docker-compose.dev.yml · .env.example · .gitignore
```

| Thư mục / file | Ai sở hữu | Ghi chú |
| --- | --- | --- |
| `docs/` | master | Agent con chỉ đọc |
| `backend/` | `backend-dev` | Gồm cả `backend/avatars/` (12 nhân vật mặc định + manifest) và `backend/Dockerfile` |
| `frontend/` | `frontend-dev` | Gồm cả `frontend/Dockerfile`, `frontend/nginx.conf`, 12 hình của mã phòng |
| File ở thư mục gốc | master | `docker-compose*.yml`, `.env.example`, `.gitignore`, `README.md` |

**Quy trình của master**, 4 giai đoạn; mỗi giai đoạn giao song song cho cả hai agent con:

1. **Khung và logic lõi**: BE dựng project, `schemas.py`, các module thuần trong `game/` kèm test; FE dựng project, `contract.ts`, mock client, router và các view rỗng.
2. **Tính năng đầy đủ** theo *Nhiệm vụ BE* và *Nhiệm vụ FE*.
3. **Docker**: mỗi agent làm Dockerfile của mình; master viết các file compose và `.env.example`.
4. **Tích hợp**: master chạy Docker Compose, làm danh sách *Kiểm thử chung*, giao lỗi về đúng agent.

Sau mỗi giai đoạn, master chạy test của cả hai bên, kiểm tra `git diff` không có file nào nằm ngoài phạm vi của agent đã sửa, rồi commit.

## Luật chơi đã chốt

| Hạng mục | Quyết định |
| --- | --- |
| Phòng | Không cần tài khoản. Ai cũng tạo được phòng và trở thành **chủ phòng**. Nhiều phòng chạy song song, tối đa 30 người chơi mỗi phòng |
| Vé | Lưới 5 × 5, ô giữa (hàng 3, cột 3) là FREE |
| Số lớn nhất `max_number` (M) | Chủ phòng đặt khi tạo phòng: số nguyên **> 30**, không giới hạn trên, mặc định 100. **Mọi toán hạng, kết quả và số trên vé đều ≤ M** |
| Phạm vi số | 1–M, không trùng số trong một vé |
| Cột của vé | R (tập số dùng được) sắp tăng dần, chia đều thành 5 nhóm liên tiếp. Ví dụ M = 100, bật đủ phép: cột 1: 1–20 · cột 2: 21–40 · cột 3: 41–60 · cột 4: 61–80 · cột 5: 81–100 (xem *Thuật toán* mục 2) |
| Điều kiện thắng | Đủ 5 ô trên 1 hàng ngang, cột dọc hoặc đường chéo (12 đường). Hệ thống tự phát hiện |
| Kết thúc ván | Ngay sau số đầu tiên tạo ra bingo. Mọi người bingo ở cùng số đó đều thắng |
| Phép tính | Chủ phòng bật/tắt + − × : khi tạo phòng |
| Cộng, trừ | Toán hạng và kết quả trong 1–M. Trừ không ra 0 hoặc số âm |
| Nhân, chia | Bảng cửu chương 1–10, và mọi số (kể cả số bị chia) ≤ M. Chia luôn chia hết |
| Chuyển câu `next_mode` | Chủ phòng chọn khi tạo phòng: **`auto`** (mặc định) — hết reveal mà chưa bingo, hoặc sau khi Bỏ qua, server tự ra câu tiếp theo; **`manual`** — chờ chủ phòng bấm Câu tiếp theo |
| Liên kết toán và bingo | Hệ thống bốc số trước, rồi sinh phép tính có kết quả bằng số đó. Số được khoanh = kết quả đúng |
| Đáp án | 4 lựa chọn A/B/C/D, đúng 1 đáp án đúng |
| Người trả lời | Chọn khi bắt đầu ván, không đổi giữa ván: **fixed** (chủ phòng chọn 1 người luôn trả lời) hoặc **random** (ngẫu nhiên thuần, không cân bằng lượt) |
| Help | Hệ thống chọn ngẫu nhiên người khác chưa thử câu này, giữ nguyên phép tính, sinh A/B/C/D mới. Không giới hạn số lần |
| Trả lời sai | Cùng người trả lời lại với A/B/C/D mới. Sai 2 lần liên tiếp thì tự động chuyển người khác như Help |
| Đếm ngược | Tùy chọn khi tạo phòng, mặc định tắt. Hết giờ coi như Help |
| Bỏ qua | Chủ phòng có nút Bỏ qua: số đó quay lại kho chưa bốc |
| Điểm | Không có hệ thống điểm |
| Khoanh số | Trả lời đúng thì số được khoanh trên vé của **mọi người** có số đó, tự động |
| Reveal | Màn hình chính **và trang điều khiển của chủ phòng** lần lượt hiện vé của từng người có số đó, **`reveal_seconds` giây mỗi vé (mặc định 3, chủ phòng chỉnh được)**, có hiệu ứng vẽ vòng tròn đỏ trực tiếp cho số mới; số khoanh trước đó hiển thị tĩnh, phân biệt rõ. Màn hình người chơi chỉ hiện vé của chính mình: có số thì khoanh ô đó, không có số thì báo "Bạn không có số N" và **không** khoanh hay làm nổi ô nào |
| Nhân vật | Mỗi người chơi chọn 1 nhân vật khi vào phòng; nhân vật hiện cùng vé, khi trả lời và khi thắng (có animation) |
| Ngôn ngữ | Tiếng Việt (mặc định) và tiếng Anh |
| Môi trường | Mạng LAN, chạy bằng Docker Compose |

## Vai trò và màn hình

Không có tài khoản hay đăng nhập. Quyền của mỗi màn hình được xác định bằng **token** do server cấp khi tạo phòng hoặc vào phòng, lưu trong `localStorage` của trình duyệt.

| Màn hình | Route | Thiết bị | Ai dùng | Chức năng |
| --- | --- | --- | --- | --- |
| Trang chủ | `/` | Mọi thiết bị | Mọi người | 2 nút lớn: Tạo phòng, Vào phòng · chọn ngôn ngữ |
| Tạo phòng | `/create` | Mọi thiết bị (chủ yếu laptop / tablet) | Chủ phòng | Form cấu hình luật: phép tính, đếm ngược, số lần sai tối đa, thời gian reveal. Điền sẵn cấu hình lần trước |
| Điều khiển phòng | `/host/:pin` | Mọi thiết bị (chủ yếu laptop / tablet) | Chủ phòng | Mã phòng + QR cho người chơi · danh sách người chơi, kick · sửa cấu hình khi đang ở sảnh · chọn fixed/random rồi bắt đầu · nút Câu tiếp theo, Bỏ qua, Help, Kết thúc ván, Ván mới, Đóng phòng · mở màn hình chính |
| Màn hình chính | `/screen/:pin?token=<screen_token>` | Máy chiếu / TV / laptop (mở được trên điện thoại) | Cả phòng xem | Sảnh: PIN, mã hình, QR, danh sách người chơi kèm nhân vật · trong ván: phép tính, 4 đáp án, nhân vật và tên người đang trả lời, đồng hồ · sau khi đúng: lần lượt hiện vé có số đó với hiệu ứng khoanh · dải số đã ra · màn hình người thắng |
| Người chơi | `/play/:pin` (hoặc `/play` để nhập mã) | Điện thoại, tablet hoặc laptop | Các bé | Quét QR, chọn 3 hình hoặc nhập PIN · nhập tên · chọn nhân vật · xem vé của mình bất cứ lúc nào · xem câu hỏi · nếu được chọn: bấm A/B/C/D hoặc Help · màn hình thắng/thua |

**Responsive**: mọi màn hình phải dùng được cả trên laptop (trình duyệt desktop, chuột/bàn phím) và trên mobile web (điện thoại dọc và ngang, cảm ứng), từ bề rộng 360px tới 1920px. Không cuộn ngang; vùng bấm tối thiểu 44 × 44px; không phụ thuộc hover. Màn hình người chơi thiết kế mobile-first, trên laptop căn giữa với bề rộng tối đa hợp lý. Trang điều khiển trên điện thoại xếp thành một cột, nút điều khiển chính luôn trong tầm với. Màn hình chính tối ưu cho 1920 × 1080 nhưng co lại được trên laptop nhỏ và điện thoại (vé và đáp án vẫn đọc được).

Chủ phòng chỉ điều khiển, không có vé. Muốn chơi cùng thì vào phòng bằng thiết bị hoặc tab khác như một người chơi bình thường. Màn hình chính chỉ hiển thị, không thao tác; mở từ nút trên trang điều khiển, dùng được ở tab khác hoặc máy khác.

## Phòng chơi

- **Tạo phòng**: `POST /api/rooms` kèm cấu hình và địa chỉ join. Server sinh mã phòng gồm PIN và mã hình (xem *Mã phòng*), cùng `host_token` và `screen_token`. FE lưu `host_token` vào `localStorage` theo PIN rồi chuyển tới `/host/<pin>`; tải lại trang vẫn điều khiển được.
- **Ai giữ `host_token` là chủ phòng.** Mất token (xóa dữ liệu trình duyệt, đổi máy) thì không điều khiển được phòng đó nữa và phải tạo phòng mới. Không có cơ chế chuyển quyền, chấp nhận được vì chỉ dùng trong LAN.
- Chủ phòng mở nhiều tab điều khiển cùng lúc (cùng token) thì mọi tab nhận cùng sự kiện.
- **Nhiều phòng song song**: mỗi phòng có một `GameEngine` độc lập (state, lock, timer riêng). Giới hạn `MAX_ROOMS` (mặc định 20); vượt quá trả 503 `too_many_rooms`.
- **Không có database**: cấu hình thuộc về từng phòng và chỉ nằm trong bộ nhớ. Trình duyệt của chủ phòng tự nhớ cấu hình và địa chỉ join lần trước trong `localStorage` để điền sẵn lần sau.
- **Dọn phòng**: chủ phòng bấm Đóng phòng, hoặc phòng không có kết nối nào (host, screen, player) trong `ROOM_IDLE_MINUTES` phút (mặc định 30) thì server xóa phòng và gửi `room_closed` cho ai còn kết nối. Khởi động lại server thì mất mọi phòng.

### Mã phòng: số và hình

Mỗi phòng có **hai mã** cùng trỏ tới một phòng. Màn hình chính và trang điều khiển hiện **cả hai** cạnh nhau; bé nhập kiểu nào cũng vào được.

| Mã | Dạng | Dành cho |
| --- | --- | --- |
| PIN | 4 chữ số, 1000–9999, hiển thị cách quãng: **4 7 2 9** | Bé biết đọc số, người lớn |
| Mã hình | 3 hình theo thứ tự, chọn từ bộ 12 hình, không lặp hình (12 × 11 × 10 = 1.320 tổ hợp) | Bé chưa biết đọc số |

- **Bộ 12 hình**, id cố định trong hợp đồng: `apple` (táo), `banana` (chuối), `star` (ngôi sao), `sun` (mặt trời), `moon` (mặt trăng), `heart` (trái tim), `car` (ô tô), `plane` (máy bay), `ball` (quả bóng), `flower` (bông hoa), `umbrella` (cái ô), `fish` (con cá). FE vẽ thành 12 file SVG trong `frontend/src/assets/room-icons/`, mỗi hình một màu riêng dễ phân biệt. Không dùng emoji vì mỗi máy hiển thị emoji một kiểu. Tên hình dịch theo ngôn ngữ. Bộ hình này khác hẳn bộ nhân vật để bé không nhầm.
- **Định danh thật** của phòng là `room_id` (UUID) nội bộ; PIN và mã hình chỉ là biệt danh để tra ra `room_id`. Mọi token gắn với `room_id`, nên token của phòng cũ không dùng được ở phòng mới dù trùng PIN.
- **Sinh mã**: PIN và mã hình sinh ngẫu nhiên, độc lập với nhau; trùng với phòng đang mở hoặc đang trong thời gian nghỉ thì chọn lại. Bỏ các PIN dễ đoán: 4 chữ số giống nhau (1111) và dãy tăng/giảm liên tiếp (1234, 9876).
- **Thời gian nghỉ**: phòng đóng rồi thì PIN và mã hình của nó không được cấp lại trong `CODE_COOLDOWN_MINUTES` phút (mặc định 30). Ai quét QR cũ hoặc nhập mã cũ sẽ thấy "Phòng đã đóng" thay vì vào nhầm phòng khác.
- Mã giữ nguyên khi bấm Ván mới; chỉ đổi khi tạo phòng mới.
- **Hiển thị**: ở sảnh, màn hình chính hiện PIN thật to và ngay dưới là 3 hình lớn có số thứ tự 1-2-3; ở các trạng thái khác hiện bản nhỏ ở góc màn hình. Trang điều khiển hiện cả hai cạnh QR.
- **Nhập ở `/play`**: hai tab **Chọn hình** (mặc định) và **Nhập số**. Chọn hình: lưới 12 hình to, bấm lần lượt 3 hình, mỗi hình hiện vào 3 ô trống đánh số 1-2-3, có nút xóa hình vừa chọn; đủ 3 hình thì gọi `GET /api/rooms/lookup` để lấy PIN rồi đi tiếp. Nhập số: 4 ô số to, bàn phím số (`inputmode="numeric"`), gõ xong tự nhảy ô.

## Luồng game và state machine

Mỗi phòng có 5 trạng thái; mọi chuyển trạng thái do server quyết định, client chỉ gửi yêu cầu và hiển thị theo `phase` nhận được.

```text
            Tạo phòng
                │
                ▼
   ┌──────► lobby ──Bắt đầu──► question ──Đúng──► reveal
   │                           ▲   │  ▲             │   │
 Ván mới            Câu tiếp theo  │  └ Sai/Help/   │   │ Chưa bingo
   │                           │   │    hết giờ     │   ▼
   │                           │   Bỏ qua           │  ready ──► question
   │                           │   ▼                │
   │                          ready                 │ Có bingo
   │                                                ▼
   └──────────────────────────────────────────── finished
```

Vòng chính là question → reveal → ready → question; bảng dưới liệt kê đầy đủ điều kiện chuyển.

| Trạng thái (`phase`) | Ý nghĩa | Chuyển sang | Khi nào |
| --- | --- | --- | --- |
| `lobby` | Phòng vừa tạo; người chơi vào phòng và nhận vé ngay khi vào | `question` | Chủ phòng chọn fixed/random rồi bấm Bắt đầu (cần ≥ 1 người chơi) |
| `question` | Đang có câu hỏi, 1 người được chỉ định trả lời | `question` | Trả lời sai, Help, hết giờ, người trả lời mất kết nối: đổi đáp án hoặc đổi người, vẫn là câu đó |
| | | `reveal` | Trả lời đúng |
| | | `ready` | `manual`: chủ phòng bấm Bỏ qua (số quay lại kho) |
| | | `question` | `auto`: chủ phòng bấm Bỏ qua → số quay lại kho, server ra ngay câu mới |
| `reveal` | Màn hình chính và trang host lần lượt hiện vé có số vừa ra, `reveal_seconds` giây mỗi vé | `finished` | Hết thời gian reveal và có người bingo |
| | | `ready` | `manual`: hết thời gian reveal, chưa ai bingo |
| | | `question` | `auto`: hết thời gian reveal, chưa ai bingo → server ra ngay câu mới |
| `ready` | Chờ chủ phòng | `question` | Chủ phòng bấm Câu tiếp theo |
| `finished` | Hiển thị người thắng và đường thắng | `lobby` | Chủ phòng bấm Ván mới (giữ người chơi và mã phòng, sinh vé mới) |

Ngoài ra: ở `question`, `reveal`, `ready`, chủ phòng bấm Kết thúc ván thì chuyển `finished` (không có người thắng). Ở mọi trạng thái, Đóng phòng thì xóa phòng. Khi bấm Bắt đầu, server tự bốc số và tạo câu hỏi đầu tiên, không cần bấm Câu tiếp theo. Ở `auto`, nếu kho bốc đã hết khi cần ra câu mới thì chuyển `ready` (chủ phòng chỉ còn Kết thúc ván); `ready` vẫn nhận Câu tiếp theo ở cả hai chế độ.

Người chơi chỉ vào phòng được khi `phase = lobby`. Người đã vào có thể kết nối lại ở bất kỳ trạng thái nào bằng `player_token`.

## Thuật toán chi tiết

Toàn bộ logic dưới đây chạy ở BE, riêng cho từng phòng; FE không tự tính đáp án, không tự đánh dấu ô. Dùng `secrets.SystemRandom()` cho mọi lựa chọn ngẫu nhiên.

### 1. Tập số khả dụng R

Tùy phép tính được bật và `max_number` = M, chỉ một số giá trị có thể là kết quả. R là hợp của:

- Cộng: 2–M (a, b ≥ 1, a + b ≤ M)
- Trừ: 1–(M−1) (a ≤ M, b ≥ 1)
- Nhân: mọi tích a × b ≤ M với a, b trong 1–10
- Chia: mọi n trong 1–10 có ít nhất một b hợp lệ với a = n × b ≤ M

Cấu hình hợp lệ khi bật ít nhất 1 phép, M > 30 và |R| ≥ 25. Ví dụ M = 100, chỉ bật nhân thì R có 42 số, vẫn hợp lệ; M = 31 chỉ bật nhân thì R chỉ có 22 số, không hợp lệ.

M không có giới hạn trên, nên BE không được dựng R hay kho bốc thành danh sách đầy đủ khi M lớn: cộng/trừ cho R là các đoạn liên tiếp, nhân/chia có tối đa vài chục số; nhóm cột, sinh vé và bốc số làm trên đoạn số. FE phải hiển thị được số nhiều chữ số trong ô vé và nút đáp án (tự thu cỡ chữ).

### 2. Sinh vé (khi người chơi vào phòng)

1. Sắp R tăng dần, chia thành 5 nhóm liên tiếp có kích thước chênh nhau tối đa 1 (nhóm lớn hơn ở bên trái). Khi M = 100 và bật đủ phép, R = 1–100 nên 5 nhóm đúng là 1–20, 21–40, … , 81–100.
2. Cột c lấy ngẫu nhiên 5 số khác nhau từ nhóm c (cột 3 lấy 4 số), sắp tăng dần từ trên xuống.
3. Ô [2][2] (đếm từ 0) là FREE, lưu giá trị `0`.
4. Vé lưu ở server dạng `int[5][5]`, gửi riêng cho chủ vé.

### 3. Bốc số

Kho bốc = các số thuộc R, chưa ra, và **có trên ít nhất một vé đang chơi** (cấu hình `draw_only_card_numbers`, mặc định bật, để ván ít người không phải trả lời hàng loạt câu mà không ai có số). Chọn ngẫu nhiên đều 1 số. Số bị Bỏ qua quay lại kho nhưng không được chọn ngay ở câu kế tiếp nếu kho còn số khác.

### 4. Sinh phép tính cho số n

Chọn ngẫu nhiên đều 1 phép trong các phép được bật mà ra được n, rồi:

| Phép | Cách sinh | Hiển thị |
| --- | --- | --- |
| Cộng | a ngẫu nhiên trong 1…n−1, b = n − a | `a + b = ?` |
| Trừ | b ngẫu nhiên trong 1…M−n, a = n + b | `a − b = ?` |
| Nhân | chọn ngẫu nhiên 1 cặp (a, b) trong 1–10 có a × b = n; ưu tiên cặp không chứa 1 nếu có | `a × b = ?` |
| Chia | b ngẫu nhiên trong 2–10 với n × b ≤ M (n = 1 thì cho phép b = 1), a = n × b | `a : b = ?` (tiếng Anh: `a ÷ b = ?`) |

Phép tính giữ nguyên suốt câu hỏi, kể cả khi đổi người hoặc sinh lại đáp án.

### 5. Sinh 4 đáp án

1. Ứng viên sai: n ± 1, n ± 2, n ± 10, n đảo chữ số (nếu có 2 chữ số khác nhau); thêm theo phép: cộng/trừ dùng nhầm phép (a − b hoặc a + b), nhân a × (b ± 1) và (a ± 1) × b, chia n ± 1.
2. Lọc: trong 1–M, khác n, không trùng nhau, không thuộc tập **đã dùng làm đáp án sai trước đó của câu này**.
3. Thiếu thì bù số ngẫu nhiên trong khoảng n ± 15 (vẫn trong 1–M) theo cùng điều kiện lọc; vẫn cạn thì mở rộng ra cả 1–M.
4. Lấy ngẫu nhiên 3 số sai, đặt n vào vị trí ngẫu nhiên; khi sinh lại, vị trí của n phải khác lần trước.
5. Server chỉ gửi giá trị của A/B/C/D, **không gửi** lựa chọn nào đúng.

### 6. Chọn người trả lời

- Chế độ chốt khi bắt đầu ván: `fixed` (kèm `fixed_player_id`) hoặc `random`.
- Đầu mỗi câu: `fixed` thì chọn người cố định; nếu người đó đang mất kết nối thì chọn ngẫu nhiên người đang kết nối. `random` thì chọn ngẫu nhiên đều trong những người đang kết nối.
- Mỗi câu có tập `tried` (người đã thử). Khi cần đổi người (Help, sai `max_wrong` lần, hết giờ, mất kết nối): chọn ngẫu nhiên trong người đang kết nối không thuộc `tried`. Nếu không còn ai, xóa `tried` (chỉ giữ người hiện tại) rồi chọn lại. Nếu chỉ có 1 người kết nối, người đó tiếp tục với đáp án mới.
- Mỗi lần đổi người: đếm số lần sai về 0, sinh lại A/B/C/D, đặt lại đồng hồ.
- Chủ phòng cũng có nút Help để đổi người thay người chơi.

### 7. Xử lý câu trả lời

- Chỉ nhận `submit_answer` từ người đang được chỉ định, đúng `question_id` và `attempt` hiện tại; còn lại trả lỗi `not_your_turn` hoặc `stale_question`.
- Đúng: thêm n vào `drawn`, tính danh sách vé chứa n, chuyển `reveal`.
- Sai: `wrong_count += 1`. Nếu `wrong_count < max_wrong` (mặc định 2) thì cùng người, sinh A/B/C/D mới. Nếu đạt `max_wrong` thì đổi người.

### 8. Reveal và kiểm tra bingo

- `affected` = người chơi có n trên vé, theo thứ tự vào phòng. Mỗi phần tử gồm vé, nhân vật, các ô đã khoanh trước đó, ô mới.
- Thời lượng reveal = `max(len(affected), 1) × reveal_seconds` (mặc định 3 giây). Không ai có số thì màn hình chính và trang host hiện thông báo trong `reveal_seconds` giây.
- Kiểm tra bingo bằng bitmask: đánh số ô 0–24, tính sẵn 12 mask (5 hàng, 5 cột, 2 chéo); ô được đánh dấu khi là FREE hoặc số đã ra; thắng khi `(marked & line) == line`.
- Hết thời gian reveal, nếu có người thắng thì chuyển `finished` kèm danh sách người thắng và đường thắng. Ngược lại: `manual` thì chuyển `ready`; `auto` thì bốc số và ra câu mới ngay (kho hết thì chuyển `ready`).

## QR và địa chỉ join

Địa chỉ trong QR **không cần biết trước**: mặc định lấy từ thanh địa chỉ của trình duyệt chủ phòng, và chủ phòng đổi được bất cứ lúc nào.

**Thứ tự chọn địa chỉ gốc (join base URL)**

1. Địa chỉ chủ phòng đã đặt tay trước đó, nhớ trong `localStorage` của trình duyệt chủ phòng.
2. Nếu chưa có: `window.location.origin` của trình duyệt chủ phòng tại thời điểm bấm **Tạo phòng** hoặc **Ván mới**.

FE gửi giá trị đã chọn trong body của `POST /api/rooms` và `POST /api/rooms/{pin}/new-round`. Server ghép `join_url = <base>/play/<pin>`, gửi trong `snapshot` và sự kiện `join_url_updated`. Trang điều khiển và màn hình chính đều vẽ QR từ `join_url` (thêm `?lang=<ngôn ngữ đang dùng>`), nên màn hình chính mở ở máy khác vẫn ra đúng QR.

**Khối "Địa chỉ cho người chơi" trên trang điều khiển**

- Hiện `join_url`, mã QR và nút Sao chép.
- Nút **Dùng địa chỉ hiện tại**: lấy `window.location.origin` và xóa địa chỉ đặt tay đã nhớ.
- Ô nhập để sửa tay (ví dụ `http://192.168.1.15:8080`) và nút Lưu, gọi `PUT /api/rooms/{pin}/join-base-url` và nhớ vào `localStorage` cho lần sau. Đổi được ở mọi trạng thái, kể cả giữa ván; người đã vào phòng không bị ảnh hưởng, QR trên mọi màn hình cập nhật ngay.
- **Cảnh báo localhost**: nếu host là `localhost`, `127.0.0.1` hoặc `[::1]`, hiện cảnh báo nổi bật "Điện thoại sẽ không mở được địa chỉ này", kèm các IP gợi ý từ `GET /api/network` (bấm vào để điền). Không có gợi ý thì hiện hướng dẫn ngắn cách xem IP máy (`ipconfig` trên Windows, `ipconfig getifaddr en0` trên macOS).
- Kiểm tra định dạng: phải là `http://` hoặc `https://`, có host, không có path hay query; sai thì server trả 422 `invalid_join_url`.

**Phía người chơi**: quét QR là mở thẳng `/play/<pin>`, chỉ còn nhập tên và chọn nhân vật. PIN sai hoặc phòng đã đóng thì báo lỗi và cho nhập mã tay.

Mẹo vận hành: chủ phòng mở trang bằng `http://<IP LAN>:<port>` ngay từ đầu thì QR đúng luôn, không cần chỉnh gì.

## Song ngữ

- Dùng `vue-i18n`, hai file `locales/vi.json` và `locales/en.json`, mặc định `vi`. Không để chuỗi hiển thị nào hard-code trong component.
- Nút chuyển ngôn ngữ trên mọi màn hình, lưu vào `localStorage`; tham số `?lang=` trên URL được ưu tiên.
- Server luôn trả `code` lỗi; FE dịch theo `code`, còn `message` chỉ là dự phòng.
- Phép tính do FE tự dựng từ `operator`, `a`, `b`: dấu chia hiển thị `:` ở tiếng Việt và `÷` ở tiếng Anh; nhân hiển thị `×`. Trường `text` chỉ dùng dự phòng.
- Tên nhân vật và tên 12 hình mã phòng có cả hai ngôn ngữ.

## Nhân vật và animation chiến thắng

### Bộ nhân vật

Bộ nhân vật là **dữ liệu**, không hard-code, nên thêm hoặc đổi nhân vật chỉ cần chép file ảnh và sửa manifest.

- Thư mục `backend/avatars/` gồm `manifest.json` và các file ảnh. BE serve ảnh tại `/avatars/<file>` và trả danh sách qua `GET /api/avatars`.
- Mỗi mục trong manifest:

```json
{
  "id": "capybara",
  "name": {"vi": "Chuột lang nước", "en": "Capybara"},
  "image": "capybara.svg",
  "win_animation": null,
  "color": "#C08A5B"
}
```

- `image`: PNG, WebP hoặc SVG vuông, tối thiểu 256 px, nền trong suốt. `win_animation` (tùy chọn): GIF/WebP động hoặc file Lottie JSON phát khi thắng. `color`: màu chủ đạo dùng cho viền vé và pháo giấy.
- **Bộ mặc định**: 12 nhân vật gốc, vẽ SVG đơn giản, dễ thương: chuột lang nước (capybara), mèo, thỏ, gấu, gấu trúc, cáo, chim cánh cụt, ếch, vịt, kỳ lân, khủng long, cú. Agent BE tạo các file này cùng `manifest.json` trong `backend/avatars/`; FE chỉ lấy qua API.
- **Nhân vật có bản quyền** (ví dụ Kuromi, Hello Kitty): Claude Code không vẽ lại các nhân vật này. Người dùng tự chép file ảnh mình có vào `backend/avatars/` và thêm một mục vào `manifest.json`, không cần sửa code.
- **Chọn khi vào phòng**: lưới ảnh nhân vật to, dễ bấm cho bé, có tên bên dưới. Cho phép nhiều bé chọn trùng nhân vật (tên giúp phân biệt); ảnh đã có người chọn hiện số nhỏ ở góc.
- **Hiển thị nhân vật** ở: danh sách người chơi trong sảnh, người đang trả lời (ảnh lớn), phía trên mỗi vé khi reveal (ảnh + tên, viền vé theo `color`), vé của mình trên điện thoại, và màn hình người thắng.

### Animation chiến thắng

- **Màn hình chính** (`finished`): nhân vật của người thắng phóng to giữa màn hình, nhún nhảy, xoay nhẹ, có lấp lánh xung quanh; pháo giấy (`canvas-confetti`) theo `color` của nhân vật; vé thắng hiện bên cạnh, các ô trên đường thắng sáng lần lượt. Nếu manifest có `win_animation` thì phát file đó thay cho hiệu ứng nhún nhảy. Nhiều người thắng thì lần lượt mỗi người khoảng 6 giây, lặp lại.
- **Điện thoại người thắng**: cùng hiệu ứng toàn màn hình kèm rung máy. Điện thoại người khác: hiện nhân vật và tên người thắng nhỏ hơn, kèm lời chúc mừng.
- Hiệu ứng âm thanh tùy chọn trên màn hình chính, mặc định tắt trên điện thoại.
- Tôn trọng `prefers-reduced-motion`: chỉ giữ hiệu ứng đơn giản.

## Hợp đồng REST API

REST dùng để tạo phòng, gửi lệnh của chủ phòng và cho người chơi vào phòng. Mọi thay đổi trạng thái được phát tới client qua WebSocket, nên các lệnh của chủ phòng chỉ trả `{"ok": true}`.

**Quy ước chung**

- Prefix `/api`, JSON, field dạng `snake_case`.
- Endpoint có quyền **host** cần header `Authorization: Bearer <host_token>` của đúng phòng đó; thiếu hoặc sai trả 401 `bad_token`.
- PIN không tồn tại trả 404 `room_not_found`. Gọi lệnh sai trạng thái trả 409 `invalid_phase`.
- Lỗi luôn có dạng `{"code": "<mã>", "message": "<mô tả>"}`; FE hiển thị theo `code` (xem *Song ngữ*).
- Body sai dạng mà không thuộc mã riêng nào (ví dụ `answerer_mode` lạ, body rỗng, JSON hỏng) trả 422 `invalid_request`. Field có mã riêng thì thiếu hay sai đều dùng mã đó (ví dụ thiếu `nickname` → `invalid_nickname`, thiếu `avatar_id` → `invalid_avatar`). Route không tồn tại trả 404 `not_found`, sai method trả 405 `method_not_allowed`. FE gặp mã không biết thì hiện thông báo lỗi chung.

**Cấu hình phòng (`GameConfig`)**

```json
{
  "operations": {"add": true, "sub": true, "mul": true, "div": true},
  "timer_seconds": 0,
  "max_wrong": 2,
  "reveal_seconds": 3,
  "draw_only_card_numbers": true,
  "max_number": 100,
  "next_mode": "auto"
}
```

`timer_seconds`: 0 là tắt, ngược lại 5–120. `max_wrong`: 1–5. `reveal_seconds`: 2–15, mặc định 3. `max_number`: số nguyên > 30, mặc định 100, không giới hạn trên về luật chơi; giới hạn kỹ thuật 9007199254740991 (2^53 − 1, số nguyên lớn nhất JavaScript biểu diễn chính xác). `next_mode`: `"auto"` (mặc định) hoặc `"manual"`. Không hợp lệ (không bật phép nào, `max_number` ≤ 30, hoặc |R| < 25) trả 422 `invalid_config`. Request thiếu `max_number` / `next_mode` thì server dùng giá trị mặc định.

**Endpoint** (`{pin}` là PIN của phòng)

| Method | Path | Quyền | Body | Trả về | Trạng thái hợp lệ | Lỗi riêng |
| --- | --- | --- | --- | --- | --- | --- |
| POST | `/api/rooms` | công khai | `{config, join_base_url}` | `{pin, picture_code, host_token, screen_token, join_url}` | | 422 `invalid_config`, `invalid_join_url` · 503 `too_many_rooms` |
| GET | `/api/rooms/{pin}` | công khai | | `{phase, player_count, avatar_counts}`; `avatar_counts: Record<avatar_id, number>`, chỉ gồm nhân vật có ≥ 1 người chọn | mọi lúc | |
| GET | `/api/rooms/lookup?pictures=<id>,<id>,<id>` | công khai | | `{pin}` | mọi lúc | 404 `room_not_found` (mã hình không khớp phòng nào, hoặc phòng đã đóng) |
| DELETE | `/api/rooms/{pin}` | host | | `{ok}` | mọi lúc | |
| PUT | `/api/rooms/{pin}/config` | host | `GameConfig` | `GameConfig` | `lobby` (sinh lại vé cho mọi người), `finished` | 422 `invalid_config` |
| PUT | `/api/rooms/{pin}/join-base-url` | host | `{join_base_url}` | `{join_url}` | mọi lúc | 422 `invalid_join_url` |
| DELETE | `/api/rooms/{pin}/players/{player_id}` | host | | `{ok}` | `lobby` | 404 `player_not_found` |
| POST | `/api/rooms/{pin}/start` | host | `{answerer_mode: "fixed" \| "random", fixed_player_id: string \| null}` | `{ok}` | `lobby` | 422 `no_players`, `fixed_player_required` |
| POST | `/api/rooms/{pin}/next` | host | | `{ok}` | `ready` | 409 `no_numbers_left` |
| POST | `/api/rooms/{pin}/skip` | host | | `{ok}` | `question` | |
| POST | `/api/rooms/{pin}/help` | host | | `{ok}` | `question` | |
| POST | `/api/rooms/{pin}/end` | host | | `{ok}` | `question`, `reveal`, `ready` | |
| POST | `/api/rooms/{pin}/new-round` | host | `{join_base_url}` (tùy chọn) | `{ok}` | `finished` | 422 `invalid_join_url` |
| POST | `/api/rooms/{pin}/join` | công khai | `{nickname, avatar_id}` | `{player_id, player_token}` | `lobby` | 409 `nickname_taken`, `game_in_progress`, `room_full` · 422 `invalid_nickname` (1–20 ký tự sau khi trim), `invalid_avatar` |
| GET | `/api/avatars` | công khai | | `Avatar[]` | | |
| GET | `/api/network` | công khai | | `{ips: string[], port: number}` | | |
| GET | `/api/health` | công khai | | `{ok}` | | |

Lưu ý định tuyến: khai báo `GET /api/rooms/lookup` **trước** `GET /api/rooms/{pin}` để không bị nuốt bởi route có tham số.

Static: `/avatars/<file>` là file ảnh nhân vật.

**Token**: `host_token`, `screen_token`, `player_token` là chuỗi ngẫu nhiên 32 byte (`secrets.token_urlsafe`), lưu trong bộ nhớ, gắn với `room_id`, hợp lệ đến khi phòng bị xóa; `player_token` hết hiệu lực khi người chơi bị kick. `screen_token` chỉ dùng để xem.

**`GET /api/network`** chỉ để **gợi ý** IP cho chủ phòng. Chạy ngoài Docker: các IPv4 nội bộ của máy (10.x, 172.16–31.x, 192.168.x, bỏ loopback). Chạy trong Docker (có file `/.dockerenv`): chỉ trả `LAN_IP` nếu được đặt, không trả IP của container. `port` lấy từ `APP_PORT` nếu có, không thì port server đang chạy.

## Hợp đồng WebSocket

Một endpoint duy nhất: `/ws?pin=<pin>&role=<host|screen|player>&token=<token>`. Mã đóng kết nối: 4401 token sai · 4404 phòng không tồn tại · 4403 người chơi bị kick · 4409 kết nối bị thay bằng kết nối mới của cùng người chơi (mở ở tab/thiết bị khác) · 4410 phòng đã đóng (gửi sau `room_closed`). Client **không** tự kết nối lại khi nhận 4401, 4403, 4404, 4409, 4410. Mọi message, cả hai chiều, có dạng `{"type": "<tên>", "data": {...}}`.

**Kiểu dữ liệu dùng chung**

```ts
type Phase = "lobby" | "question" | "reveal" | "ready" | "finished";
type RoomIcon = "apple" | "banana" | "star" | "sun" | "moon" | "heart" | "car" | "plane" | "ball" | "flower" | "umbrella" | "fish";
type GameConfig = {
  operations: { add: boolean; sub: boolean; mul: boolean; div: boolean };
  timer_seconds: number; max_wrong: number; reveal_seconds: number; draw_only_card_numbers: boolean;
  max_number: number;              // > 30, mặc định 100
  next_mode: "auto" | "manual";    // mặc định "auto"
};
type Avatar = { id: string; name: { vi: string; en: string }; image_url: string; win_animation_url: string | null; color: string };
type PlayerInfo = { id: string; nickname: string; avatar_id: string; connected: boolean };
type Card = number[][];            // 5x5, card[row][col], 0 = FREE tại [2][2]
type Cell = [number, number];      // [row, col], đếm từ 0
type Line = { type: "row" | "col" | "diag"; index: number }; // diag 0: trái-trên → phải-dưới, 1: phải-trên → trái-dưới
type OptionKey = "A" | "B" | "C" | "D";

type Question = {
  question_id: string;
  attempt: number;                 // tăng mỗi lần sinh lại đáp án hoặc đổi người
  text: string;                    // "7 × 8 = ?" (dự phòng; FE tự dựng từ operator, a, b)
  operator: "+" | "-" | "x" | ":";
  a: number; b: number;
  options: { key: OptionKey; value: number }[]; // luôn đủ A, B, C, D theo thứ tự
  answerer: PlayerInfo;
  deadline: string | null;         // ISO 8601 UTC, null nếu tắt đếm ngược
};

type RevealItem = { player_id: string; nickname: string; avatar_id: string; card: Card; marked_before: Cell[]; new_cell: Cell };
type Reveal = { number: number; seconds_per_card: number; started_at: string; items: RevealItem[] };
type Winner = { player_id: string; nickname: string; avatar_id: string; card: Card; marked: Cell[]; lines: Line[] };

type Snapshot = {
  pin: string; picture_code: RoomIcon[]; phase: Phase; join_url: string; config: GameConfig;
  players: PlayerInfo[];
  answerer_mode: "fixed" | "random" | null; fixed_player_id: string | null;
  drawn: number[];                 // theo thứ tự ra
  question: Question | null; reveal: Reveal | null; winners: Winner[];
  me?: PlayerInfo; card?: Card; marked?: Cell[];  // chỉ có khi role = player
};
```

**Server gửi client** (chỉ trong phạm vi một phòng)

| `type` | Gửi tới | `data` | Khi nào |
| --- | --- | --- | --- |
| `snapshot` | người vừa kết nối; tất cả khi `new-round` | `Snapshot` | Kết nối hoặc kết nối lại |
| `phase_changed` | tất cả | `{phase}` | Mỗi lần đổi trạng thái |
| `players_updated` | tất cả | `{players}` | Vào phòng, kick, mất/có kết nối |
| `config_updated` | tất cả | `{config}` | Chủ phòng lưu cấu hình |
| `join_url_updated` | tất cả | `{join_url}` | Chủ phòng đổi địa chỉ join hoặc bấm Ván mới |
| `your_card` | 1 người chơi | `{card, marked}` | Sau khi vào phòng, khi sinh lại vé |
| `game_started` | tất cả | `{answerer_mode, fixed_player_id}` | Chủ phòng bấm Bắt đầu |
| `question` | tất cả | `{question, reason}`; `reason`: `new`, `wrong`, `help`, `max_wrong`, `timeout`, `disconnect` | Câu mới, sinh lại đáp án, đổi người. Client thay thế câu hiện tại |
| `answer_result` | tất cả | `{question_id, attempt, player_id, key, value, correct}` | Sau mỗi lần trả lời |
| `number_drawn` | tất cả | `{number, drawn}` | Ngay khi trả lời đúng |
| `cell_marked` | người chơi có số | `{number, cell}` | Ngay khi trả lời đúng |
| `reveal` | tất cả | `Reveal` | Ngay sau `number_drawn` |
| `question_skipped` | tất cả | `{question_id, number}` | Chủ phòng bấm Bỏ qua |
| `game_over` | tất cả | `{reason: "bingo" \| "ended_by_host", winners}` | Kết thúc ván |
| `kicked` | 1 người chơi | `{}` | Bị kick, sau đó server đóng kết nối |
| `room_closed` | tất cả | `{reason: "closed_by_host" \| "expired"}` | Phòng bị đóng hoặc hết hạn, sau đó server đóng kết nối |
| `error` | người gửi | `{code, message}` | Message không hợp lệ. JSON hỏng, `type` lạ, `data` sai dạng, hoặc role không được gửi `type` đó: `code = invalid_message` |
| `pong` | người gửi | `{}` | Trả lời `ping` |

Với câu trả lời đúng, thứ tự gửi cố định: `answer_result` → `number_drawn` → `cell_marked` → `phase_changed {reveal}` → `reveal`.

**Client gửi server** (chỉ `role = player`; host và screen chỉ gửi `ping`, mọi lệnh của chủ phòng đi qua REST)

| `type` | `data` | Lỗi có thể nhận |
| --- | --- | --- |
| `submit_answer` | `{question_id, attempt, key}` | `not_your_turn`, `stale_question`, `invalid_phase` |
| `request_help` | `{question_id}` | `not_your_turn`, `stale_question`, `invalid_phase` |
| `ping` | `{}` | |

Client gửi `ping` mỗi 20 giây. Server coi người chơi mất kết nối khi socket đóng; nếu người đó đang trả lời thì chờ 10 giây rồi mới đổi người (`reason = disconnect`), để kịp kết nối lại khi mạng chập chờn hoặc điện thoại chuyển node WiFi mesh.

**Đồng bộ reveal**: màn hình chính tính vé đang hiện bằng `floor((now − started_at) / seconds_per_card)`, nên mở lại tab giữa chừng vẫn đúng vị trí. Server là bên quyết định lúc kết thúc reveal.

## Nhiệm vụ BE (FastAPI)

BE là nguồn sự thật duy nhất về trạng thái của mọi phòng: tạo và dọn phòng, sinh vé, bốc số, sinh câu hỏi, chấm đáp án, chọn người, kiểm tra bingo, và phát sự kiện đúng theo hợp đồng.

**Công nghệ**: Python 3.12, FastAPI, Uvicorn (`uvicorn[standard]`), Pydantic v2, `pydantic-settings`, pytest + httpx. WebSocket thuần của FastAPI, không dùng Socket.IO. **Không dùng database**, không có tài khoản.

**Cấu trúc thư mục**

```text
backend/
  app/
    main.py            # tạo app, router, /ws, /avatars, serve static + SPA fallback (khi không dùng Docker)
    settings.py        # MAX_ROOMS, ROOM_IDLE_MINUTES, CODE_COOLDOWN_MINUTES, LAN_IP, APP_PORT, AVATARS_DIR, STATIC_DIR
    schemas.py         # Pydantic model khớp 100% hợp đồng
    tokens.py          # sinh token, dependency kiểm tra host token theo PIN
    rooms.py           # RoomManager: room_id, PIN, mã hình, tạo / tìm / xóa phòng, dọn phòng idle
    avatars.py         # đọc và kiểm tra manifest
    network.py         # IP gợi ý cho /api/network
    game/
      numbers.py       # tập R theo phép được bật
      cards.py         # sinh vé
      questions.py     # sinh phép tính cho số n
      options.py       # sinh 4 đáp án
      bingo.py         # bitmask, 12 đường thắng
      engine.py        # GameEngine của 1 phòng: state machine, timer, chọn người
    ws/manager.py      # kết nối theo PIN + role, send / broadcast trong phòng
    api/rooms.py · api/host.py · api/public.py
  avatars/             # manifest.json + ảnh (BE tạo bộ mặc định)
  tests/
  Dockerfile · .dockerignore · requirements.txt
```

**Công việc**

- [ ] Khởi tạo project, `settings.py`, `requirements.txt`, CORS cho `http://localhost:5173` khi dev.
- [ ] `schemas.py`: mọi kiểu trong *Hợp đồng REST API* và *Hợp đồng WebSocket*, tên field đúng từng chữ.
- [ ] Các module thuần trong `game/` (không I/O, nhận random generator làm tham số để test được) theo mục *Thuật toán chi tiết*.
- [ ] `GameEngine` cho mỗi phòng: giữ state trong bộ nhớ, mọi thao tác thay đổi state của phòng đi qua **`asyncio.Lock` riêng của phòng**. Timer đếm ngược, timer reveal, timer chờ 10 giây khi mất kết nối dùng `asyncio.Task` hủy được; hủy timer cũ mỗi khi câu hỏi hoặc người trả lời đổi.
- [ ] `RoomManager`: `room_id` nội bộ, PIN và mã hình theo mục *Mã phòng* (kèm thời gian nghỉ), endpoint lookup mã hình, giới hạn `MAX_ROOMS`, task nền mỗi phút xóa phòng không có kết nối nào quá `ROOM_IDLE_MINUTES`; khi xóa thì hủy mọi timer, gửi `room_closed` và đóng socket.
- [ ] `tokens.py`: host / screen / player token theo mục *Hợp đồng REST API*; host token của phòng A không dùng được cho phòng B.
- [ ] `ws/manager.py`: map kết nối theo PIN, role và `player_id`; người chơi kết nối lại thì thay socket cũ; host và screen được mở nhiều kết nối; gửi `snapshot` ngay khi kết nối.
- [ ] REST endpoint đúng bảng, kiểm tra quyền và `phase`, trả lỗi đúng `code`.
- [ ] Địa chỉ join: kiểm tra `join_base_url`, ghép `join_url`, endpoint đổi địa chỉ và sự kiện `join_url_updated`.
- [ ] Nhân vật: tạo 12 nhân vật SVG mặc định và `manifest.json` trong `backend/avatars/`; đọc và kiểm tra manifest khi khởi động (id không trùng, file ảnh tồn tại, báo lỗi rõ nếu sai). Mục sai thì bỏ qua và ghi log cảnh báo nêu rõ lỗi, server vẫn chạy với các mục hợp lệ; chỉ dừng khởi động khi `manifest.json` không đọc được hoặc không còn nhân vật hợp lệ nào; serve `/avatars`; `GET /api/avatars`; kiểm tra `avatar_id` khi vào phòng.
- [ ] `GET /api/network` và `GET /api/health` theo hợp đồng.
- [ ] Không bao giờ gửi đáp án đúng xuống client trước khi trả lời đúng; không tin bất kỳ trạng thái ô nào từ client.
- [ ] Khi có `STATIC_DIR` (chạy không Docker): serve bản build FE, các route `/`, `/create`, `/host/*`, `/screen/*`, `/play`, `/play/*` trả `index.html`.
- [ ] Log mỗi sự kiện chính kèm PIN (tạo phòng, vào phòng, câu mới, trả lời, đổi người, bingo, đóng phòng).
- [ ] File Docker của BE theo mục *Docker*.

**Test bắt buộc**

- [ ] Vé: 1000 vé ngẫu nhiên với mọi tổ hợp phép hợp lệ đều đúng cột, không trùng, ô giữa là 0.
- [ ] Phép tính: với mọi tổ hợp phép và mọi n thuộc R, phép sinh ra có kết quả đúng n, toán hạng trong phạm vi, trừ không ra số âm, chia chia hết, nhân/chia trong bảng 1–10.
- [ ] Đáp án: 4 giá trị khác nhau trong 1–100, đúng 1 bằng n; sinh lại thì vị trí của n đổi và không lặp đáp án sai đã dùng.
- [ ] Bingo: đủ 12 đường, các trường hợp gần thắng không bị tính thắng.
- [ ] Tích hợp bằng `TestClient` WebSocket: tạo phòng → 3 người vào → bắt đầu chế độ random → trả lời sai 2 lần thì đổi người → Help → trả lời đúng → nhận đúng thứ tự sự kiện → chơi đến khi có bingo.
- [ ] Chế độ fixed: người cố định trả lời mọi câu; Help đổi sang người khác; câu kế tiếp quay lại người cố định.
- [ ] Phòng: 2 phòng chạy song song không ảnh hưởng nhau; host token phòng A gọi lệnh phòng B bị 401; vượt `MAX_ROOMS` bị 503; PIN và mã hình không trùng giữa các phòng đang mở và không bị cấp lại trong thời gian nghỉ; token phòng cũ không vào được phòng mới dù trùng PIN; lookup mã hình trả đúng PIN; phòng idle bị dọn và client nhận `room_closed`.
- [ ] Vào phòng với `avatar_id` sai trả `invalid_avatar`.

**Hoàn thành khi**: `pytest` xanh, và chạy `uvicorn app.main:app --host 0.0.0.0 --port 8000` rồi chơi được trọn một ván bằng một client thử (script Python `tests/manual_client.py`, nhận base URL làm tham số để dùng được cả với `http://localhost:8000` lẫn `http://localhost:8080` qua nginx).

## Nhiệm vụ FE (Vue)

FE hiển thị đúng theo `phase` và sự kiện từ server, không tự tính đáp án hay tự đánh dấu ô. Trong lúc BE chưa xong, FE chạy hoàn toàn bằng mock client.

**Công nghệ**: Vue 3 (Composition API, `<script setup>`), Vite, TypeScript, Pinia, Vue Router, `vue-i18n`, `qrcode`, `canvas-confetti`, `lottie-web` (chỉ lazy-load khi cần phát `win_animation` dạng Lottie JSON), `vitest` (dev). Không bắt buộc UI library. Màn hình người chơi thiết kế mobile-first cho trẻ em (nút to, chữ to, màu tươi); màn hình chính thiết kế cho 1920 × 1080.

**Cấu trúc thư mục**

```text
frontend/src/
  api/contract.ts      # type khớp 100% hợp đồng
  api/rest.ts          # gọi REST, tự gắn Bearer host token khi cần
  api/gameClient.ts    # interface GameClient { connect(pin, role, token); on(type, fn); send(type, data); close() }
  api/wsClient.ts      # bản thật: tự kết nối lại (backoff 1s → 10s), ping 20s
  api/mock/            # bản giả: engine giả lập server + REST giả, bật bằng VITE_USE_MOCK=true
  i18n/index.ts · i18n/locales/vi.json · i18n/locales/en.json
  stores/game.ts       # Pinia: nhận snapshot rồi áp dụng từng sự kiện
  stores/session.ts    # token theo PIN, cấu hình và địa chỉ join lần trước (localStorage)
  views/HomeView.vue · CreateRoomView.vue · HostView.vue · ScreenView.vue · PlayView.vue
  components/BingoCard.vue · QuestionPanel.vue · AnswerButtons.vue · PlayerList.vue · DrawnNumbers.vue
             RevealCarousel.vue · Countdown.vue · AvatarPicker.vue · AvatarBadge.vue · JoinLinkPanel.vue
             WinnerCelebration.vue · LanguageSwitch.vue · RoomCodeDisplay.vue · RoomCodeInput.vue
  assets/room-icons/   # 12 SVG cho mã hình
```

**Component quan trọng: `BingoCard.vue`**

- Props: `card: Card`, `marked: Cell[]`, `newCell?: Cell`, `animateNew: boolean`, `winningLines?: Line[]`, `player?: {nickname, avatar_id}`, `size: "sm" | "md" | "lg"`.
- Phần đầu vé: nhân vật và tên người chơi; viền vé theo `color` của nhân vật.
- Ô FREE hiển thị chữ "FREE" và luôn được coi là đã khoanh.
- **Ô đã khoanh trước đó**: vòng tròn đỏ tĩnh, nét vừa, hơi mờ.
- **Ô mới**: vòng tròn SVG được **vẽ trực tiếp** bằng animation `stroke-dashoffset` (khoảng 1,2 giây, bắt đầu 0,5 giây sau khi vé xuất hiện), nét đậm hơn, nền ô sáng lên và nhấp nháy nhẹ suốt thời gian vé hiển thị, để phân biệt rõ với các ô cũ.
- `winningLines`: tô nổi bật các ô thuộc đường thắng.

**Trang chủ và Tạo phòng (`/`, `/create`)**

- Trang chủ: 2 nút lớn Tạo phòng và Vào phòng, nút chuyển ngôn ngữ.
- Tạo phòng: form `GameConfig` (bật ít nhất 1 phép, hiển thị lỗi `invalid_config`), điền sẵn cấu hình lần trước; bấm Tạo thì gọi `POST /api/rooms` kèm `join_base_url` theo mục *QR và địa chỉ join*, lưu `host_token` và `screen_token` theo PIN, chuyển tới `/host/<pin>`.

**Điều khiển phòng (`/host/:pin`)**

- Không có `host_token` cho PIN này thì hiện "Bạn không phải chủ phòng này" kèm nút về trang chủ.
- `JoinLinkPanel` theo mục *QR và địa chỉ join*, kèm `RoomCodeDisplay` (PIN + mã hình).
- Danh sách người chơi kèm nhân vật, nút kick; sửa cấu hình khi `phase` là `lobby` hoặc `finished`.
- Hộp thoại Bắt đầu: chọn **Cố định** (kèm dropdown chọn người) hoặc **Ngẫu nhiên**.
- Form cấu hình (tạo phòng và sửa ở sảnh) có thêm: **Số lớn nhất** (`max_number`, ô số, > 30, báo lỗi ngay khi ≤ 30 hoặc |R| < 25) và **Chuyển câu** (`next_mode`: Tự động / Thủ công). `reveal_seconds` hiển thị là "Thời gian xem mỗi vé (giây)".
- `reveal`: trang điều khiển cũng hiện `RevealCarousel` giống màn hình chính (cùng đồng bộ theo `started_at`), co gọn theo bề rộng màn hình, kèm tiêu đề "Vé 2/5" và "Số mới: 56".
- Bảng điều khiển: câu hỏi hiện tại, người đang trả lời, số đã ra; các nút Câu tiếp theo, Bỏ qua, Help, Kết thúc ván, Ván mới chỉ bật khi `phase` cho phép (ở `auto`, nút Câu tiếp theo chỉ hiện khi `phase = ready`, tức lúc kho bốc đã hết); nút Mở màn hình chính (mở `/screen/<pin>?token=<screen_token>` ở tab mới); nút Đóng phòng có hộp thoại xác nhận.

**Màn hình chính (`/screen/:pin`)**

- `lobby`: PIN và mã hình thật to theo mục *Mã phòng* (`RoomCodeDisplay`), mã QR từ `join_url`, danh sách người chơi kèm nhân vật cập nhật realtime.
- `question`: phép tính chữ lớn, 4 ô A/B/C/D, nhân vật và tên người đang trả lời, đồng hồ (nếu bật); khi `answer_result` sai thì ô đó rung đỏ rồi hiện bộ đáp án mới.
- `reveal`: `RevealCarousel` hiện lần lượt từng vé trong `reveal.items`, mỗi vé `seconds_per_card` giây, tiêu đề "Vé 2/5" và "Số mới: 56", dùng `BingoCard` với `newCell` và `animateNew`. Không ai có số thì hiện "Không ai có số 56".
- Luôn có dải danh sách số đã ra; mã phòng nhỏ ở góc.
- `finished`: `WinnerCelebration` theo mục *Nhân vật và animation chiến thắng*.

**Người chơi (`/play/:pin`, `/play`)**

- `/play` cho chọn 3 hình hoặc nhập PIN theo mục *Mã phòng* (`RoomCodeInput`); `/play/:pin` (từ QR) vào thẳng bước nhập tên rồi `AvatarPicker`.
- Lưu `player_token` vào `localStorage` theo PIN để tự kết nối lại khi tải lại trang.
- Hai tab: **Vé của tôi** (luôn xem được, các ô đã khoanh, ô mới nhất có animation khi nhận `cell_marked`) và **Câu hỏi**.
- `reveal` trên màn hình người chơi: chỉ hiện vé của chính mình. Nếu nhận `cell_marked` cho số vừa ra (`cell_marked.number === reveal.number`) thì vẽ vòng tròn ô đó; nếu không thì hiện "Bạn không có số N" và **không** truyền `newCell` / không animate ô nào. `newCell` chỉ được lấy từ `cell_marked` của đúng lượt hiện tại, không bao giờ lấy từ ô đã khoanh ở lượt trước.
- Khi mình là người trả lời: chuyển sang tab Câu hỏi, 4 nút A/B/C/D to, nút Help, đồng hồ, rung máy (`navigator.vibrate`) nếu có. Khóa nút sau khi bấm cho đến khi nhận `answer_result` hoặc `question` mới.
- Khi người khác trả lời: hiển thị phép tính, nhân vật và "<tên> đang trả lời", không có nút bấm.
- Màn hình thắng/thua khi `game_over`; "Bạn đã bị mời ra" khi `kicked`; "Phòng đã đóng" kèm nút về trang chủ khi `room_closed`.

**Nhân vật**: lấy danh sách qua `GET /api/avatars` (ảnh do BE tạo). Mock client dùng ảnh tạm: hình tròn màu kèm chữ cái đầu, cùng dạng dữ liệu `Avatar`.

**Mock client** (`api/mock/`): giả lập đúng hợp đồng, gồm tạo phòng (sinh PIN và mã hình), lookup mã hình, và 3 người chơi ảo (tự trả lời ngẫu nhiên sau 2 giây khi đến lượt), dùng chung thuật toán đơn giản để sinh vé và phép tính. Đủ để chạy hết luồng `lobby → question → reveal → ready → finished` mà không cần BE. Khi tích hợp chỉ cần đặt `VITE_USE_MOCK=false`.

**Build**: `npm run build` (gồm `vue-tsc --noEmit`) xuất ra `dist/` (dùng trong Docker); `npm run build:embed` xuất ra `../backend/static` (chạy không Docker). `vite.config.ts` proxy `/api`, `/ws` (bật `ws: true`), `/avatars` sang `VITE_PROXY_TARGET` (mặc định `http://localhost:8000`).

**Hoàn thành khi**: với mock, tạo phòng và chơi trọn một ván trên cả 3 màn hình; reveal hiện đúng `reveal_seconds` giây mỗi vé (mặc định 3) trên cả màn hình chính và trang host và ô mới được vẽ vòng tròn trực tiếp; tải lại trang người chơi giữa ván vẫn thấy vé và các ô đã khoanh; đổi ngôn ngữ giữa ván không mất trạng thái; mở `/play/<pin>` vào thẳng bước nhập tên; vào phòng bằng mã hình được.

## Docker

Cách chạy chính thức là Docker Compose với 2 container: `frontend` (nginx) là cổng duy nhất mở ra mạng LAN và proxy mọi request API, WebSocket, ảnh nhân vật sang `backend`.

| Service | Image | Vai trò | Cổng |
| --- | --- | --- | --- |
| `frontend` | build bằng `node:22-alpine`, chạy bằng `nginx:1.27-alpine` | Serve bản build Vue; proxy `/api`, `/ws`, `/avatars` sang backend | 80 trong container, map ra host `${APP_PORT:-8080}` |
| `backend` | `python:3.12-slim` | FastAPI + Uvicorn | 8000, chỉ trong mạng nội bộ của compose, không publish |

**File cần có**

```text
docker-compose.yml          # chạy thật (master)
docker-compose.dev.yml      # phát triển, hot reload (master)
.env.example                # (master)
backend/Dockerfile          # (backend-dev)
backend/.dockerignore       # (backend-dev)
frontend/Dockerfile         # (frontend-dev)
frontend/nginx.conf         # (frontend-dev)
frontend/.dockerignore      # (frontend-dev)
```

**`backend/Dockerfile`**

- `python:3.12-slim`, cài `requirements.txt` với `--no-cache-dir`, chạy bằng user không phải root.
- Lệnh chạy: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*`.
- **Bắt buộc 1 worker**, vì mọi phòng nằm trong bộ nhớ của tiến trình. Không dùng `--workers`, không chạy nhiều replica.
- `HEALTHCHECK` gọi `GET /api/health` bằng `python -c` (image slim không có curl).

**`frontend/Dockerfile`** (multi-stage)

- Stage build: `npm ci`, rồi `npm run build` với `VITE_USE_MOCK=false`.
- Stage chạy: chép `dist` vào `/usr/share/nginx/html`, chép `nginx.conf`.

**`frontend/nginx.conf`** (phần bắt buộc)

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;

  location /api/     { proxy_pass http://backend:8000; proxy_set_header Host $host; proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; }
  location /avatars/ { proxy_pass http://backend:8000; }

  location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }

  location /assets/  { expires 1y; add_header Cache-Control "public, immutable"; }
  location /         { try_files $uri $uri/ /index.html; add_header Cache-Control "no-cache"; }
}
```

**`docker-compose.yml`**

```yaml
services:
  backend:
    build: ./backend
    env_file: .env
    volumes:
      - ./backend/avatars:/app/avatars
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "${APP_PORT:-8080}:80"
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped
```

**`.env.example`**

```text
APP_PORT=8080
MAX_ROOMS=20
ROOM_IDLE_MINUTES=30
CODE_COOLDOWN_MINUTES=30
LAN_IP=                 # tùy chọn, có thể để trống: chỉ dùng để gợi ý IP cho chủ phòng
AVATARS_DIR=/app/avatars
```

**Về QR khi chạy Docker**: không cần biết trước IP. QR lấy địa chỉ từ thanh địa chỉ của chủ phòng hoặc địa chỉ chủ phòng đặt lúc runtime (xem *QR và địa chỉ join*). `LAN_IP` chỉ dùng để gợi ý khi chủ phòng lỡ mở bằng `localhost`, vì trong container backend không tự thấy được IP LAN của máy.

**`docker-compose.dev.yml`** (phát triển)

- `backend`: chạy `uvicorn ... --reload`, mount `./backend/app` và `./backend/avatars` vào container.
- `frontend`: dùng image `node:22-alpine`, mount `./frontend`, chạy `npm run dev -- --host 0.0.0.0`, publish cổng 5173, đặt `VITE_PROXY_TARGET=http://backend:8000`; `node_modules` dùng volume riêng để không bị thư mục máy host ghi đè.

**Lệnh sử dụng**

1. Chạy thật: `cp .env.example .env`, rồi `docker compose up -d --build`. Mở trang chủ bằng IP LAN của máy, ví dụ `http://192.168.1.15:8080`, để QR đúng ngay.
2. Phát triển: `docker compose -f docker-compose.dev.yml up --build`, mở `http://<IP LAN>:5173`.
3. Thêm nhân vật: chép ảnh vào `backend/avatars/`, sửa `manifest.json`, rồi `docker compose restart backend`.
4. Xem log: `docker compose logs -f backend`.

**Phân công**

- [ ] BE (`backend-dev`): `backend/Dockerfile`, `backend/.dockerignore`.
- [ ] FE (`frontend-dev`): `frontend/Dockerfile`, `frontend/nginx.conf`, `frontend/.dockerignore`; `vite.config.ts` đọc `VITE_PROXY_TARGET`.
- [ ] Master: `docker-compose.yml`, `docker-compose.dev.yml`, `.env.example`, `.gitignore`.

**Hoàn thành khi**

- [ ] Trên máy sạch chỉ có Docker: `docker compose up -d --build` chạy được, cả hai container ở trạng thái healthy/running.
- [ ] Tạo phòng và chơi trọn một ván từ điện thoại trong cùng WiFi qua `http://<IP LAN>:8080`; QR mở thẳng trang chơi.
- [ ] WebSocket không bị nginx cắt khi để yên 5 phút.
- [ ] Thêm một nhân vật chỉ bằng file ảnh + manifest, `docker compose restart backend` là thấy ngay.
- [ ] Trên Windows/macOS với Docker Desktop: điện thoại vẫn truy cập được (nhớ cho phép Docker Desktop qua firewall).

## Chạy không dùng Docker và kiểm thử chung

**Phát triển không dùng Docker**

1. BE: `cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
2. FE: `cd frontend && VITE_USE_MOCK=false npm run dev -- --host`.
3. Điện thoại trong cùng WiFi mở `http://<IP LAN của máy>:5173`.

**Chạy thật không dùng Docker**: `npm run build:embed`, rồi chạy Uvicorn với `STATIC_DIR=static` (không `--reload`) và mở `http://<IP LAN>:8000`. Cho phép Python qua firewall ở chế độ mạng Private. Tránh WiFi công cộng hoặc mạng Guest có bật cách ly thiết bị; nếu cần, phát hotspot từ chính máy chạy server.

**Kiểm thử chung trước khi dùng**

- [ ] 3 điện thoại thật vào phòng (1 bằng QR, 1 bằng mã hình, 1 bằng PIN), chơi trọn 1 ván ở chế độ random và 1 ván ở chế độ fixed.
- [ ] 2 người tạo 2 phòng cùng lúc trên 2 máy khác nhau, chơi song song không ảnh hưởng nhau.
- [ ] Tắt WiFi một điện thoại đang được chỉ định trả lời: sau 10 giây hệ thống đổi người; bật lại thì vẫn thấy vé và ô đã khoanh.
- [ ] Bật đếm ngược 10 giây: hết giờ thì đổi người.
- [ ] Chỉ bật phép nhân và chia: vé và phép tính vẫn hợp lệ, ván vẫn kết thúc được.
- [ ] Đóng rồi mở lại màn hình chính đúng lúc đang reveal: tiếp tục đúng vé đang hiện.
- [ ] Chủ phòng tải lại trang điều khiển giữa ván: vẫn điều khiển được.
- [ ] Chủ phòng bấm Đóng phòng: mọi điện thoại hiện "Phòng đã đóng"; quét lại QR cũ cũng thấy "Phòng đã đóng".
