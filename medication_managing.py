import streamlit as st
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

today = datetime.today()
two_months_later = today + timedelta(days=60) # 往後推算 60 天

st.set_page_config(page_title="診所藥品管理", page_icon="💊",
                    layout='wide')
st.title('庫存管理')

if "save_success" in st.session_state and st.session_state.save_success:
    st.success(st.session_state.save_success)
    st.toast("資料已寫入暫存區", icon="💾")
    # 秀完之後立刻清空這個狀態，避免下次改格子時又重複跳出來
    st.session_state.save_success = ""

# 2. 處理「儲存失敗 / 系統錯誤」的提示
if "save_error" in st.session_state and st.session_state.save_error:
    st.error(st.session_state.save_error)   # 穩穩地在最上方秀出紅色的錯誤框
    st.session_state.save_error = ""    # 顯示完一樣立刻清空

if "staff_id_val" not in st.session_state:
    st.session_state.staff_id_val = ""  # 員編預設值
if "qty_val" not in st.session_state:
    st.session_state.qty_val = 0          # 數量預設值


#load data
@st.cache_data #優先執行記憶體(快取)
def load_data():
    df = pd.read_csv("盛軒效期管理 - 藥品總表.csv")
    return df
df0 = load_data()

@st.cache_data #優先執行記憶體(快取)
def load_data1():
    df = pd.read_csv("盛軒 - 出庫入庫清單.csv")
    return df
df1 = load_data1()

#@st.cache_data會讓 Streamlit 認定這個檔案「永遠不變」，就算你按了暫存存入第 6 筆，刷新後的表格依然只會抓第一次載入的舊狀態。
def temp_data():
    df = pd.read_csv("暫存出入庫清單.csv")
    return df
df2 = temp_data()

def load_official_data():
    official_path = "盛軒 - 出庫入庫清單.csv"  
    if os.path.exists(official_path):
        return pd.read_csv(official_path, encoding='utf-8-sig')
    return pd.DataFrame()

def data_analyze():
    analyze_path = "盛軒效期管理 - 藥品總表.csv"
    if not os.path.exists(analyze_path):
        return pd.DataFrame()
    df_med = pd.read_csv(analyze_path, encoding='utf-8-sig')
    
    # 2. 讀取正式出入庫清單 (呼叫你之前寫的方法)
    df_history = load_official_data()
    # 3. 如果有歷史出入庫紀錄，就開始整理進去
    if not df_history.empty:
        # 依照藥品六編加總所有的出入庫數量
        df_sum = df_history.groupby("六編/藥品簡稱")["數量"].sum()
        change_volumes = df_med["六編/藥品簡稱"].map(df_sum).fillna(0)
        df_med["庫存"] = df_med["庫存"] + change_volumes
        df_min_expire = df_history.groupby("六編/藥品簡稱")["效期"].min()
        df_med["最早效期(含過期)"] = df_med["六編/藥品簡稱"].map(df_min_expire).fillna(df_med["最早效期(含過期)"])

        # 1. 計算效期前先把字串轉成時間型態
        df_history["效期_datetime"] = pd.to_datetime(df_history["效期"], errors='coerce')

        # 2. 定義時間區間條件
        df_near_condition = (df_history["效期_datetime"] >= today) & (df_history["效期_datetime"] <= two_months_later)
        df_expired_condition = df_history["效期_datetime"] < today
        
        # 3. 分流篩選出「近效資料集」與「已過期資料集」
        df_history_near = df_history[df_near_condition]
        df_history_expired = df_history[df_expired_condition]
        
        # 4. 💡【分門別類計算】依據「六編/藥品簡稱」各自加總與找最小值
        # 分別算出每款藥品自己的：最早近效期、近效總異動量、已過期總異動量
        near_date_map = df_history_near.groupby("六編/藥品簡稱")["效期"].min()
        near_sum_map = df_history_near.groupby("六編/藥品簡稱")["數量"].sum()
        expired_sum_map = df_history_expired.groupby("六編/藥品簡稱")["數量"].sum()
        #使用 .nunique() 計算每款藥品有幾「種」不同的效期日期
        near_types_map = df_history_near.groupby("六編/藥品簡稱")["效期"].nunique()
        expired_types_map = df_history_expired.groupby("六編/藥品簡稱")["效期"].nunique()
        near_cnt = df_med["近效總量"].fillna(0).astype(int)
        exp_cnt = df_med["已過期總量"].fillna(0).astype(int)
       
        # 5. 💡【精準對照更新】利用 .map() 把數據個別填入對應的藥品格子裡
        #    如果找不到紀錄，日期填 '-' 或維持原樣，數量則補 0 
        df_med["近效未過期"] = df_med["六編/藥品簡稱"].map(near_date_map).fillna('-')
        df_med["近效總量"] = df_med["六編/藥品簡稱"].map(near_sum_map).fillna(0)
        df_med["已過期總量"] = df_med["六編/藥品簡稱"].map(expired_sum_map).fillna(0)
        df_med["近效效期種數"] = df_med["六編/藥品簡稱"].map(near_types_map).fillna(0).astype(int)
        df_med["已過期效期種數"] = df_med["六編/藥品簡稱"].map(expired_types_map).fillna(0).astype(int)
        df_med["_tmp_near"] = near_cnt
        df_med["_tmp_expired"] = exp_cnt
        def make_warning_text(row):
            near = row["_tmp_near"]
            exp = row["_tmp_expired"]
            
            if near > 0 and exp > 0:
                return f"近效{near}, 過期{exp}"
            elif near > 0:
                return f"近效{near}"
            elif exp > 0:
                return f"過期{exp}"
            else:
                return "" # 0的時候留白
            # 4. 執行整欄判斷
        df_med["效期警示"] = df_med.apply(make_warning_text, axis=1)

        # 5. 清理暫存欄位
        df_med.drop(columns=["_tmp_near", "_tmp_expired"], inplace=True)
    return df_med

def generate_serial_number(file_path, prefix, date_str):
    """
    自動計算流水號的輔助函數
    file_path: 暫存 CSV 的檔案路徑
    prefix: 'A' 或 'B'
    date_str: 當天日期字串 (例如 '20260621')
    """
    count = 1
    full_prefix = f"{prefix}{date_str}" # 組合起來像 "A20260621"
    
    if os.path.exists(file_path):
        try:
            df_history = pd.read_csv(file_path, encoding='utf-8-sig')
            if "單號" in df_history.columns and not df_history.empty:
                # 篩選出所有開頭符合今天前綴的單號，並轉為字串
                today_serials = df_history["單號"].astype(str)
                today_matches = today_serials[today_serials.str.startswith(full_prefix)]
                
                if not today_matches.empty:
                    max_num = 0
                    for serial in today_matches:
                        try:
                            # 移除前綴字，留下尾數數字 (例如 "A202606210001" -> 1)
                            num_part = int(serial.replace(full_prefix, ""))
                            if num_part > max_num:
                                max_num = num_part
                        except ValueError:
                            continue
                    count = max_num + 1
        except Exception:
            pass

    # 💡 :04d 代表補足四位數流水號 (1 -> "0001")；若要三位數可改為 :03d
    suffix = f"{count:04d}"
    return f"{full_prefix}{suffix}"

#=======================================================================================================================
st.sidebar.header("🔍 資料查詢篩選器")

# 1. 關鍵字搜尋（品名或六編）
search_keyword = st.sidebar.text_input("藥品名稱 / 六編關鍵字", value="", placeholder="請輸入關鍵字...")

# 2. 類別多選 (預設全選)
all_categories = list(df0["類別"].unique())
selected_categories = st.sidebar.multiselect("藥品類別篩選", options=all_categories, default=all_categories)

# 3. 進銷存紀錄的時間篩選
st.sidebar.subheader("進銷存時間篩選")
today_date = datetime.today().date()
start_date = st.sidebar.date_input("開始日期", today_date - timedelta(days=30))
end_date = st.sidebar.date_input("結束日期", today_date)

# 4. 出入庫狀態篩選（僅影響進銷存清單）
filter_status = st.sidebar.selectbox("出入庫狀態", ["全部", "入庫", "出庫"])


# ==================== 資料基礎讀取與過濾邏輯 ====================

# 讀取計算後的原始資料
df_official_raw = load_official_data()  # 歷史進銷存
df_med_analyzed = data_analyze()       # 藥品總表

# 💡 建立通用的關鍵字與類別遮罩函數，確保三個表格連動時邏輯一致
def apply_basic_filter(df):
    if df.empty:
        return df
    new_df = df.copy()
    if search_keyword:
        new_df = new_df[
            new_df["藥品名稱"].str.contains(search_keyword, case=False, na=False) |
            new_df["六編/藥品簡稱"].str.contains(search_keyword, case=False, na=False)
        ]
    if selected_categories:
        new_df = new_df[new_df["類別"].isin(selected_categories)]
    return new_df

# --- A. 過濾【藥品總表】 ---
df_med_filtered = apply_basic_filter(df_med_analyzed)


# --- B. 產生並過濾【效期庫存總覽】 (關鍵核心) ---
if not df_official_raw.empty:
    # 分品項、分效期進行數量加總
    df_expiry_summary = df_official_raw.groupby(
        ["六編/藥品簡稱", "藥品名稱", "類別", "效期"]
    )["數量"].sum().reset_index()
    
    # 重新命名欄位讓名稱更直覺
    df_expiry_summary.rename(columns={"數量": "該效期剩餘庫存"}, inplace=True)
    
    # 排除庫存為 0 的資料（若藥師想看已扣完的可以把這行註解掉）
    df_expiry_summary = df_expiry_summary[df_expiry_summary["該效期剩餘庫存"] != 0]
    
    # 依效期由近到遠排序
    df_expiry_summary = df_expiry_summary.sort_values(by=["效期", "六編/藥品簡稱"])
    
    # 套用側邊欄篩選
    df_expiry_filtered = apply_basic_filter(df_expiry_summary)
else:
    df_expiry_filtered = pd.DataFrame()


# --- C. 過濾【進銷存清單】 (包含時間與狀態) ---
df_history_filtered = df_official_raw.copy()
if not df_history_filtered.empty:
    df_history_filtered["日期_date"] = pd.to_datetime(df_history_filtered["日期"]).dt.date
    date_condition = (df_history_filtered["日期_date"] >= start_date) & (df_history_filtered["日期_date"] <= end_date)
    df_history_filtered = df_history_filtered[date_condition]
    
    # 基本篩選
    df_history_filtered = apply_basic_filter(df_history_filtered)
    
    # 狀態篩選
    if filter_status != "全部":
        df_history_filtered = df_history_filtered[df_history_filtered["出入庫"] == filter_status]
        
    df_history_filtered.drop(columns=["日期_date"], errors="ignore", inplace=True)
#==================================================================================================================================================

with st.container():
    st.subheader("📝 輸入表單")
    
    col1, col2, col3, col_list = st.columns([1, 1, 1, 2])
    
    with col1:
        input_date = st.date_input("日期", datetime.now(), disabled=True)
        staff_id = st.text_input("員編", value=st.session_state.staff_id_val)
        status = st.radio("出入庫狀態", ["入庫", "出庫"], horizontal=True)

    with col2:
        listc = df0["類別"]
        set1 = set(listc)
        category_list=list(set1)
        category = st.selectbox("類別", category_list)

        codem = df0[df0["類別"]==category]
        code_list = codem["六編/藥品簡稱"]
        med_code = st.selectbox("六編/藥品簡稱",code_list)

        current_med_row = codem[codem["六編/藥品簡稱"] == med_code]

        if not current_med_row.empty:
            # 1. 撈出品名
            default_drug_name = current_med_row["藥品名稱"].values[0]
            
            # 2. 💡【新加入】順便撈出該藥品對應的「單位」與「庫存校正」
            #    .values[0] 可以精準抓出該欄位的第一筆文字或數字
            unit_val = current_med_row["單位"].values[0]
            stock_val = current_med_row["庫存校正"].values[0]
            min_unit_val = current_med_row["最小單位"].values[0] if "最小單位" in current_med_row.columns else "顆"
        else:
            default_drug_name = "找不到對應品名"
            unit_val = "盒"
            stock_val = 0
            min_unit_val = '顆'

        # 使用 st.text_input 呈現唯讀的灰色品名框
        drug_name = st.text_input("藥品名稱", value=default_drug_name, disabled=True)

    with col3:
        expire_date = st.date_input("效期", datetime.now())
        qty_col1, qty_col2 = st.columns([3, 2])
        with qty_col1:
            qty = st.number_input("數量", value=st.session_state.qty_val, step=1)
        with qty_col2:
            # 加上空白標籤區塊，讓文字與左邊的數字輸入框水平對齊
            st.markdown("<div style='padding-top: 40px;'></div>", unsafe_allow_html=True)
            
            # 💡 直接帶入剛剛撈出來、屬於該藥品專屬的單位與庫存量
            st.markdown(f"**一** {unit_val}/{stock_val}{min_unit_val}")    

        if st.button("💾 暫存紀錄", type="primary", use_container_width=True):
            if not staff_id.strip() or qty <= 0:
                st.session_state.save_error="❌ 儲存失敗！請確認「藥品名稱」、「數量」與「員編」皆已完整輸入。"
                st.rerun()
            else:
        #2. 將畫面上的各個變數，打包成一筆新資料（字典格式）
        #根據出庫或入庫，自動調整數量正負值（出庫為負數，入庫為正數）
                final_qty = -qty if status == "出庫" else qty
                temp_csv_path = "暫存出入庫清單.csv"
                prefix = "A" if status == "入庫" else "B"
                date_str = input_date.strftime("%Y%m%d") # 格式化為 20260621
                new_serial = generate_serial_number(temp_csv_path, prefix, date_str)

                new_row = {
                "單號": new_serial,
                "日期": input_date.strftime("%Y-%m-%d"), # 格式化日期為 2026-06-16
                "出入庫": status,
                "六編/藥品簡稱": med_code,
                "類別": category,
                "藥品名稱": drug_name,
                "數量": final_qty,
                "效期": expire_date.strftime("%Y-%m-%d"),
                "員編": staff_id
                }
        # 3. 將單筆資料轉換為 Pandas DataFrame
                new_df = pd.DataFrame([new_row])
        # 5. 核心邏輯：判斷檔案是否存在
        # 如果檔案還不存在，代表是第一次寫入，需要寫入欄位名稱 (header=True)
        # 如果檔案已經存在，就直接附加在後面，不需要再寫欄位名稱 (header=False)
                file_exists = os.path.exists(temp_csv_path)
                try:
                    new_df.to_csv(
                    temp_csv_path, 
                    mode='a',                # 'a' 代表 append 附加
                    index=False,             # 不寫入 Pandas 的流水號索引
                    header=not file_exists,  # 如果檔案存在就不寫 header，不存在就寫
                    encoding='utf-8-sig'     # 使用 utf-8-sig 可以防止 Excel 打開時變亂碼
                    )
        # 6. 跳出綠色成功提示
                    st.session_state.save_success = f"✅ 暫存成功！已將 **{drug_name}** ({status} {qty} ) 寫入暫存盤點檔。"
                    st.session_state.qty_val = 0
                    st.session_state.staff_id_val = ""
                    st.rerun()
            
                except Exception as e:
                    st.session_state.save_error=f"❌ 寫入檔案時發生錯誤：{e}"
                    st.rerun()

        if st.button("儲存紀錄", type="primary", use_container_width=True):
            official_csv_path = "盛軒 - 出庫入庫清單.csv"  # 正式檔路徑
            temp_csv_path = "暫存出入庫清單.csv"           # 暫存檔路徑
            df_history = load_official_data()
            df_temp = temp_data()  # 讀取目前正在輸入/暫存的品項
            if not df_temp.empty:
        # 2. 把歷史紀錄跟本次要存的紀錄合併在一起算（只抓需要計算的欄位）
                cols = ["六編/藥品簡稱", "藥品名稱", "效期", "數量"]
        
        # 確保兩張表的欄位一致，並排除歷史表為空的情況
                df_h_sub = df_history[cols] if not df_history.empty else pd.DataFrame(columns=cols)
                df_t_sub = df_temp[cols]
        
        # 串接起來模擬儲存後的總庫存狀況
                df_future = pd.concat([df_h_sub, df_t_sub], ignore_index=True)
        
        # 3. 💡【核心防呆】：依照「六編」與「效期」雙條件進行分類加總
        #    這能算出每一款藥品在各個效期「儲存後」的預估剩餘量
                df_future_sum = df_future.groupby(["六編/藥品簡稱", "藥品名稱", "效期"])["數量"].sum().reset_index()
        
        # 4. 找出有沒有任何一個效期的庫存總和 < 0
                df_negative = df_future_sum[df_future_sum["數量"] < 0]
        
        # 5. 🚨 判斷攔截
                if not df_negative.empty:
                    st.error("❌ 儲存失敗：扣庫存超限！以下藥品在該效期的總庫存將變為負數：")
            
            # 整理一下漂亮的表格秀給藥師看是哪項藥品、哪個效期爆了
                    df_error_show = df_negative.rename(columns={"數量": "預估庫存(負數)"})
                    st.dataframe(df_error_show, use_container_width=True, hide_index=True)
            
            # 💡 直接利用 st.stop() 攔截，後續的寫入 CSV 程式碼就不會被執行！
                    st.stop()
                try:
                    # 1. 讀取目前所有的暫存資料
                    temp_df = pd.read_csv(temp_csv_path, encoding='utf-8-sig')
                    
                    # 2. 判斷正式檔案是否存在
                    official_exists = os.path.exists(official_csv_path)
                    
                    # 3. 將暫存區的所有資料，用 'a' (append) 模式整批附加到正式大檔後面
                    temp_df.to_csv(
                    official_csv_path,
                    mode='a',
                    index=False,
                    header=not official_exists,  # 如果正式檔不存在才寫入標頭，存在就不寫
                    encoding='utf-8-sig'
                    )
                    #4. 不刪除檔案，而是用覆寫模式('w')將「空資料加標準標頭」寫入檔案
                    # 這樣做等同於「全選並清空內容」，但保留了 CSV 檔案在硬碟中
                    empty_df = pd.DataFrame(columns=temp_df.columns)
                    empty_df.to_csv(
                        temp_csv_path,
                        mode='w',
                        index=False,
                        header=True,       # 保留所有歷史欄位標題
                        encoding='utf-8-sig'
                    )

                    st.session_state.save_success = f" 轉存成功！已將 {len(temp_df)} 筆暫存資料正式寫入正式清單，並清空暫存區！"
                    st.cache_data.clear()
                    st.rerun()

                except Exception as e:
                    st.session_state.save_error = f"❌ 轉存時發生錯誤：{e}"
                    st.rerun()

    with col_list:
        st.subheader("📋 出入庫清單")
        temp_csv_path = "暫存出入庫清單.csv"  
        if not df2.empty:
            # 1. 讓最新存進去的資料顯示在表格的最上面 (反轉 DataFrame)
            df2_reversed = df2.iloc[:].copy()
            
            # 2. 在最前面插入一欄名為「選取」的布林值欄位（預設為未勾選 False）
            #    這會在網頁上自動渲染成漂亮的核取方塊（Checkbox）
            df2_reversed.insert(0, "選取", False)
            
            # 3. 使用 st.data_editor 取代 st.dataframe
            edited_df = st.data_editor(
                df2_reversed,
                use_container_width=True,
                hide_index=True,  # 隱藏 Pandas 預設的流水號索引，畫面更乾淨
                disabled=["單號","日期", "出入庫", "六編/藥品簡稱", "類別", "藥品名稱", "數量", "效期", "員編"] # 鎖定其他欄位不讓人員亂改，只允許勾選
            )
            
            # 4. 【進階應用】抓出目前到底哪幾行被勾選了
            #    edited_df["選取"] 會回傳 True 或 False，可以用來篩選資料
            selected_rows = edited_df[edited_df["選取"] == True]
            unselected_rows = edited_df[edited_df["選取"] == False]

            # 測試：如果有人勾選，就在下方顯示勾選了幾筆（之後可以做成整批刪除按鈕）
            if len(selected_rows) > 0:
                st.write(f"💡 目前已選取 {len(selected_rows)} 筆資料")

                if st.button("❌ 刪除已選取紀錄", use_container_width=True):
                    try:
                        # 核心邏輯：如果把勾選的刪掉，等於是把「沒被勾選的資料」留下來
                        # 留下來的資料要先丟棄我們為了畫畫面而加的 "選取" 欄位
                        final_save_df = unselected_rows.drop(columns=["選取"])
                        
                        # 💡【重要步驟】因為畫面原本是反轉的(最新的在上面)，存回 CSV 前要再反轉回來
                        final_save_df = final_save_df.iloc[:]
                        

                        final_save_df.to_csv(
                            temp_csv_path,
                            mode='w',          # 'w' 代表覆寫原本的檔案
                            index=False,
                            header=True,       # 重新寫入全新的標頭
                            encoding='utf-8-sig'
                            )
                        
                        # 儲存成功狀態並引發重新整理，更新畫面表格
                        st.session_state.save_success = f" 成功刪除 {len(selected_rows)} 筆選取紀錄！"
                        st.rerun()
                        
                    except Exception as e:
                        st.session_state.save_error = f"❌ 刪除時發生錯誤：{e}"
                        st.rerun()
                
        else:
            st.info("目前暫存區尚無新輸入的資料。")


    
st.markdown("---")
st.subheader("📝 藥品總表")
if not df_med_filtered.empty:
    st.dataframe(df_med_filtered, use_container_width=True, hide_index=True)
else:
    st.info("💡 找不到符合條件的藥品。")

st.markdown("---")
col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("📝 進銷存清單")
    if not df_history_filtered.empty:
        st.dataframe(df_history_filtered, use_container_width=True, hide_index=True)
    else:
        st.info("💡 該篩選條件下無歷史進銷存紀錄。")
        
    st.subheader("⏳ 效期庫存總覽 (分品項+同效期加總)")
    if not df_expiry_filtered.empty:
        st.dataframe(df_expiry_filtered, use_container_width=True, hide_index=True)
    else:
        st.info("💡 目前無效期庫存資料，或無符合篩選條件的品項。")
with col2:
    # ==================== 1. 近效品項表格 ====================
    st.subheader("📝 近效兩個月內品項")
    
    # 篩選條件：有近效日期且不為 '-'
    if not df_med_filtered.empty:
        df_near_expiry = df_med_filtered[df_med_filtered["近效未過期"] != '-'][
            ["六編/藥品簡稱", "藥品名稱", "類別", "近效未過期", "近效總量"]
        ]
    else:
        df_near_expiry = pd.DataFrame()
        
    if not df_near_expiry.empty:
        # 依據近效期由近到遠排序，方便藥師優先處理
        df_near_expiry = df_near_expiry.sort_values(by="近效未過期")
        st.dataframe(df_near_expiry, use_container_width=True, hide_index=True)
    else:
        st.info("🟢 無近效品項，藥品狀態良好")
    # ==================== 2. 庫存警示表格 (未過期庫存 < 安全量) ====================
    st.subheader("⚠️ 庫存低於安全量")
    
    if not df_med_filtered.empty and "安全量" in df_med_filtered.columns:
        df_stock_warning = df_med_filtered.copy()
        
        # 💡 A. 計算各品項的「未過期總庫存」
        unexpired_stock_map = {}
        if not df_official_raw.empty:
            df_history_cp = df_official_raw.copy()
            # 轉換效期為時間型態以利比較
            df_history_cp["效期_dt"] = pd.to_datetime(df_history_cp["效期"], errors='coerce')
            
            # 關鍵篩選：只留「效期大於或等於今天」的未過期紀錄
            df_valid_expiry = df_history_cp[df_history_cp["效期_dt"] >= pd.to_datetime(today)]
            
            # 分品項加總未過期的數量
            unexpired_stock_map = df_valid_expiry.groupby("六編/藥品簡稱")["數量"].sum().to_dict()
        
        # 💡 B. 將計算結果對照回總表，若無未過期紀錄則基本庫存為 0
        # 注意：這裡要加上原始藥品總表的基本庫存（有些藥品可能原本就有初始庫存，若您的庫存完全由出入庫清單計算，則直接 map 即可）
        # 根據您原先 data_analyze() 的邏輯，我們比照辦理：
        df_stock_warning["未過期庫存"] = df_stock_warning["六編/藥品簡稱"].map(unexpired_stock_map).fillna(0)
        # 如果您的原始總表內本來就有基礎底數(如開辦庫存)，請改用下行：
        # df_stock_warning["未過期庫存"] = df_stock_warning["庫存"] - df_stock_warning["六編/藥品簡稱"].map(df_history_cp[df_history_cp["效期_dt"] < pd.to_datetime(today)].groupby("六編/藥品簡稱")["數量"].sum()).fillna(0)

        # 💡 C. 轉數字防呆與條件篩選
        df_stock_warning["安全量_num"] = pd.to_numeric(df_stock_warning["安全量"], errors='coerce')
        df_stock_warning["未過期庫存_num"] = pd.to_numeric(df_stock_warning["未過期庫存"], errors='coerce')
        
        # 篩選條件：有設安全量，且「未過期庫存」嚴格小於「安全量」
        warning_cond = df_stock_warning["安全量_num"].notna() & (df_stock_warning["未過期庫存_num"] < df_stock_warning["安全量_num"])
        
        df_warning_show = df_stock_warning[warning_cond][
            ["六編/藥品簡稱", "藥品名稱", "安全量", "未過期庫存"]
        ]
    else:
        df_warning_show = pd.DataFrame()
        
    if not df_warning_show.empty:
        # 依據缺藥嚴重程度排序
        df_warning_show = df_warning_show.sort_values(by="未過期庫存")
        st.dataframe(df_warning_show, use_container_width=True, hide_index=True)
        st.error(f"🚨 注意：有 {len(df_warning_show)} 項藥品的「可用未過期庫存」已低於安全水位，請安排補貨！")
    else:
        st.success("無低於安全量之藥品")