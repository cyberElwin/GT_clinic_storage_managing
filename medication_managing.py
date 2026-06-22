import streamlit as st
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os

today = datetime.today()
two_months_later = today + timedelta(days=60) # 往後推算 60 天

st.set_page_config(page_title="診所藥品效期庫存管理系統", page_icon="💊", layout='wide')

# 套用全域自訂樣式：優化表格字體與區塊間距
st.markdown("""
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    h1 { color: #1E3A8A; font-weight: 700; margin-bottom: 1rem; }
    h3 { color: #2C3E50; font-weight: 600; padding-bottom: 5px; border-bottom: 2px solid #ECF0F1; }
    /* 讓 metric 的標題和數字更好看 */
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

st.title('診所藥品效期庫存管理系統')

# 1. 處理成功與失敗提示
if "save_success" in st.session_state and st.session_state.save_success:
    st.success(st.session_state.save_success)
    st.toast("資料已寫入暫存區", icon="💾")
    st.session_state.save_success = ""

if "save_error" in st.session_state and st.session_state.save_error:
    st.error(st.session_state.save_error)   
    st.session_state.save_error = ""    

if "staff_id_val" not in st.session_state:
    st.session_state.staff_id_val = ""  
if "qty_val" not in st.session_state:
    st.session_state.qty_val = 0          


# ------------------ 資料讀取與計算邏輯 ------------------
@st.cache_data 
def load_data():
    df = pd.read_csv("盛軒效期管理 - 藥品總表.csv")
    return df
df0 = load_data()

@st.cache_data 
def load_data1():
    df = pd.read_csv("盛軒 - 出庫入庫清單.csv")
    return df
df1 = load_data1()

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
    
    df_history = load_official_data()
    if not df_history.empty:
        df_sum = df_history.groupby("六編/藥品簡稱")["數量"].sum()
        df_med["庫存"] = df_med["庫存"] + df_med["六編/藥品簡稱"].map(df_sum).fillna(0)
        
        df_min_expire = df_history.groupby("六編/藥品簡稱")["效期"].min()
        df_med["最早效期(含過期)"] = df_med["六編/藥品簡稱"].map(df_min_expire).fillna(df_med["最早效期(含過期)"])

        df_history["效期_datetime"] = pd.to_datetime(df_history["效期"], errors='coerce')

        df_near_condition = (df_history["效期_datetime"] >= today) & (df_history["效期_datetime"] <= two_months_later)
        df_expired_condition = df_history["效期_datetime"] < today
        
        df_history_near = df_history[df_near_condition]
        df_history_expired = df_history[df_expired_condition]
        
        near_date_map = df_history_near.groupby("六編/藥品簡稱")["效期"].min()
        near_sum_map = df_history_near.groupby("六編/藥品簡稱")["數量"].sum()
        expired_sum_map = df_history_expired.groupby("六編/藥品簡稱")["數量"].sum()
        
        near_types_map = df_history_near.groupby("六編/藥品簡稱")["效期"].nunique()
        expired_types_map = df_history_expired.groupby("六編/藥品簡稱")["效期"].nunique()
       
        df_med["近效未過期"] = df_med["六編/藥品簡稱"].map(near_date_map).fillna('-')
        df_med["近效總量"] = df_med["六編/藥品簡稱"].map(near_sum_map).fillna(0)
        df_med["已過期總量"] = df_med["六編/藥品簡稱"].map(expired_sum_map).fillna(0)
        df_med["近效效期種數"] = df_med["六編/藥品簡稱"].map(near_types_map).fillna(0).astype(int)
        df_med["已過期效期種數"] = df_med["六編/藥品簡稱"].map(expired_types_map).fillna(0).astype(int)
        
        # 直接使用剛算好的新欄位進行 apply
        def make_warning_text(row):
            near = int(row["近效總量"])
            exp = int(row["已過期總量"])
            if near > 0 and exp > 0:
                return f"近效{near}, 過期{exp}"
            elif near > 0:
                return f"近效{near}"
            elif exp > 0:
                return f"過期{exp}"
            else:
                return "" 
                
        df_med["效期警示"] = df_med.apply(make_warning_text, axis=1)
    return df_med

def generate_serial_number(file_path, prefix, date_str):
    count = 1
    full_prefix = f"{prefix}{date_str}" 
    if os.path.exists(file_path):
        try:
            df_history = pd.read_csv(file_path, encoding='utf-8-sig')
            if "單號" in df_history.columns and not df_history.empty:
                today_serials = df_history["單號"].astype(str)
                today_matches = today_serials[today_serials.str.startswith(full_prefix)]
                if not today_matches.empty:
                    max_num = 0
                    for serial in today_matches:
                        try:
                            num_part = int(serial.replace(full_prefix, ""))
                            if num_part > max_num:
                                max_num = num_part
                        except ValueError:
                            continue
                    count = max_num + 1
        except Exception:
            pass
    suffix = f"{count:04d}"
    return f"{full_prefix}{suffix}"

# ------------------ 側邊欄篩選器 ------------------
st.sidebar.header("🔍 資料查詢篩選器")
search_keyword = st.sidebar.text_input("藥品名稱 / 六編關鍵字", value="", placeholder="請輸入關鍵字...")
all_categories = list(df0["類別"].unique())
selected_categories = st.sidebar.multiselect("藥品類別篩選", options=all_categories, default=all_categories)

st.sidebar.subheader("進銷存時間篩選")
today_date = datetime.today().date()
start_date = st.sidebar.date_input("開始日期", today_date - timedelta(days=30))
end_date = st.sidebar.date_input("結束日期", today_date)
filter_status = st.sidebar.selectbox("出入庫狀態", ["全部", "入庫", "出庫"])

# ------------------ 資料基礎讀取與過濾 ------------------
df_official_raw = load_official_data()  
df_med_analyzed = data_analyze()       

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

df_med_filtered = apply_basic_filter(df_med_analyzed)

if not df_official_raw.empty:
    df_expiry_summary = df_official_raw.groupby(["六編/藥品簡稱", "藥品名稱", "類別", "效期"])["數量"].sum().reset_index()
    df_expiry_summary.rename(columns={"數量": "該效期剩餘庫存"}, inplace=True)
    df_expiry_summary = df_expiry_summary[df_expiry_summary["該效期剩餘庫存"] != 0]
    df_expiry_summary = df_expiry_summary.sort_values(by=["效期", "六編/藥品簡稱"])
    df_expiry_filtered = apply_basic_filter(df_expiry_summary)
else:
    df_expiry_filtered = pd.DataFrame()

df_history_filtered = df_official_raw.copy()
if not df_history_filtered.empty:
    df_history_filtered["日期_date"] = pd.to_datetime(df_history_filtered["日期"]).dt.date
    date_condition = (df_history_filtered["日期_date"] >= start_date) & (df_history_filtered["日期_date"] <= end_date)
    df_history_filtered = df_history_filtered[date_condition]
    df_history_filtered = apply_basic_filter(df_history_filtered)
    if filter_status != "全部":
        df_history_filtered = df_history_filtered[df_history_filtered["出入庫"] == filter_status]
    df_history_filtered.drop(columns=["日期_date"], errors="ignore", inplace=True)

# ------------------ 🚨 預先計算 Metric 數據 ------------------
total_med_items = len(df_med_analyzed)
near_expiry_count = len(df_med_analyzed[df_med_analyzed["近效未過期"] != '-']) if not df_med_analyzed.empty else 0
expired_count = len(df_med_analyzed[df_med_analyzed["已過期總量"] > 0]) if not df_med_analyzed.empty else 0

# 計算安全庫存缺貨數
shortage_count = 0
if not df_med_analyzed.empty and "安全量" in df_med_analyzed.columns:
    df_history_cp = df_official_raw.copy()
    if not df_history_cp.empty:
        df_history_cp["效期_dt"] = pd.to_datetime(df_history_cp["效期"], errors='coerce')
        df_valid_expiry = df_history_cp[df_history_cp["效期_dt"] >= pd.to_datetime(today)]
        unexpired_stock_map = df_valid_expiry.groupby("六編/藥品簡稱")["數量"].sum().to_dict()
    else:
        unexpired_stock_map = {}
    
    med_copy = df_med_analyzed.copy()
    med_copy["未過期庫存"] = med_copy["六編/藥品簡稱"].map(unexpired_stock_map).fillna(0)
    med_copy["安全量_num"] = pd.to_numeric(med_copy["安全量"], errors='coerce')
    med_copy["未過期庫存_num"] = pd.to_numeric(med_copy["未過期庫存"], errors='coerce')
    shortage_count = len(med_copy[med_copy["安全量_num"].notna() & (med_copy["未過期庫存_num"] < med_copy["安全量_num"])])

# ==================== ✨ VISUAL VISUAL: METRIC DASHBOARD ====================
st.markdown("### 📊 庫存動態關鍵指標")
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric(" 總藥品品項", f"{total_med_items} 項")
m_col2.metric(" 近效期品項 (2M)", f"{near_expiry_count} 項", delta=f"{near_expiry_count} 需注意" if near_expiry_count > 0 else "安全", delta_color="inverse" if near_expiry_count > 0 else "normal")
m_col3.metric(" 已過期藥品", f"{expired_count} 項", delta="已失效" if expired_count > 0 else "無過期品", delta_color="inverse" if expired_count > 0 else "normal")
m_col4.metric(" 低於安全量品項", f"{shortage_count} 品項", delta="請安排補貨" if shortage_count > 0 else "庫存充足", delta_color="inverse" if shortage_count > 0 else "normal")
st.markdown("---")

# ------------------ 輸入表單區塊 ------------------
with st.container():
    st.markdown("### 📝 異動登錄表單")
    col1, col2, col3, col_list = st.columns([1, 1, 1, 2])
    
    with col1:
        input_date = st.date_input("日期", datetime.now(), disabled=True)
        staff_id = st.text_input("員編", value=st.session_state.staff_id_val)
        status = st.radio("出入庫狀態", ["入庫", "出庫"], horizontal=True)

    with col2:
        category_list = list(set(df0["類別"]))
        category = st.selectbox("類別", category_list)
        codem = df0[df0["類別"] == category]
        code_list = codem["六編/藥品簡稱"]
        med_code = st.selectbox("六編/藥品簡稱", code_list)

        current_med_row = codem[codem["六編/藥品簡稱"] == med_code]
        if not current_med_row.empty:
            default_drug_name = current_med_row["藥品名稱"].values[0]
            unit_val = current_med_row["單位"].values[0]
            stock_val = current_med_row["庫存校正"].values[0]
            min_unit_val = current_med_row["最小單位"].values[0] if "最小單位" in current_med_row.columns else "顆"
        else:
            default_drug_name = "找不到對應品名"
            unit_val = "盒"
            stock_val = 0
            min_unit_val = '顆'

        drug_name = st.text_input("藥品名稱", value=default_drug_name, disabled=True)

    with col3:
        expire_date = st.date_input("效期", datetime.now())
        qty_col1, qty_col2 = st.columns([3, 2])
        with qty_col1:
            qty = st.number_input("數量", value=st.session_state.qty_val, step=1)
        with qty_col2:
            st.markdown("<div style='padding-top: 40px;'></div>", unsafe_allow_html=True)
            st.markdown(f"**一** {unit_val}/{stock_val}{min_unit_val}")    

        if st.button("暫存紀錄", type="primary", use_container_width=True):
            if not staff_id.strip() or qty <= 0:
                st.session_state.save_error = "❌ 儲存失敗！請確認「藥品名稱」、「數量」與「員編」皆已完整輸入。"
                st.rerun()
            else:
                final_qty = -qty if status == "出庫" else qty
                temp_csv_path = "暫存出入庫清單.csv"
                prefix = "A" if status == "入庫" else "B"
                date_str = input_date.strftime("%Y%m%d") 
                new_serial = generate_serial_number(temp_csv_path, prefix, date_str)

                new_row = {
                    "單號": new_serial, "日期": input_date.strftime("%Y-%m-%d"), "出入庫": status,
                    "六編/藥品簡稱": med_code, "類別": category, "藥品名稱": drug_name,
                    "數量": final_qty, "效期": expire_date.strftime("%Y-%m-%d"), "員編": staff_id
                }
                new_df = pd.DataFrame([new_row])
                file_exists = os.path.exists(temp_csv_path)
                try:
                    new_df.to_csv(temp_csv_path, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
                    st.session_state.save_success = f"✅ 暫存成功！已將 **{drug_name}** ({status} {qty} ) 寫入暫存盤點檔。"
                    st.session_state.qty_val = 0
                    st.session_state.staff_id_val = ""
                    st.rerun()
                except Exception as e:
                    st.session_state.save_error = f"❌ 寫入檔案時發生錯誤：{e}"
                    st.rerun()

        if st.button("整批儲存", type="secondary", use_container_width=True):
            official_csv_path = "盛軒 - 出庫入庫清單.csv"  
            temp_csv_path = "暫存出入庫清單.csv"           
            df_history = load_official_data()
            df_temp = temp_data()  
            if not df_temp.empty:
                cols = ["六編/藥品簡稱", "藥品名稱", "效期", "數量"]
                df_h_sub = df_history[cols] if not df_history.empty else pd.DataFrame(columns=cols)
                df_t_sub = df_temp[cols]
                df_future = pd.concat([df_h_sub, df_t_sub], ignore_index=True)
                df_future_sum = df_future.groupby(["六編/藥品簡稱", "藥品名稱", "效期"])["數量"].sum().reset_index()
                df_negative = df_future_sum[df_future_sum["數量"] < 0]
                
                if not df_negative.empty:
                    st.error("❌ 儲存失敗：扣庫存超限！以下藥品在該效期的總庫存將變為負數：")
                    df_error_show = df_negative.rename(columns={"數量": "預估庫存(負數)"})
                    st.dataframe(df_error_show, use_container_width=True, hide_index=True)
                    st.stop()
                try:
                    temp_df = pd.read_csv(temp_csv_path, encoding='utf-8-sig')
                    official_exists = os.path.exists(official_csv_path)
                    temp_df.to_csv(official_csv_path, mode='a', index=False, header=not official_exists, encoding='utf-8-sig')
                    
                    empty_df = pd.DataFrame(columns=temp_df.columns)
                    empty_df.to_csv(temp_csv_path, mode='w', index=False, header=True, encoding='utf-8-sig')

                    st.session_state.save_success = f"🎉 轉存成功！已將 {len(temp_df)} 筆暫存資料正式寫入正式清單，並清空暫存區！"
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.session_state.save_error = f"❌ 轉存時發生錯誤：{e}"
                    st.rerun()

    with col_list:
        st.markdown("### 暫存清單")
        temp_csv_path = "暫存出入庫清單.csv"  
        if not df2.empty:
            df2_reversed = df2.iloc[:].copy()
            df2_reversed.insert(0, "選取", False)
            
            edited_df = st.data_editor(
                df2_reversed, use_container_width=True, hide_index=True,
                disabled=["單號","日期", "出入庫", "六編/藥品簡稱", "類別", "藥品名稱", "數量", "效期", "員編"] 
            )
            
            selected_rows = edited_df[edited_df["選取"] == True]
            unselected_rows = edited_df[edited_df["選取"] == False]

            if len(selected_rows) > 0:
                st.info(f"💡 目前已勾選 {len(selected_rows)} 筆資料")
                if st.button("❌ 刪除已選取紀錄", use_container_width=True):
                    try:
                        final_save_df = unselected_rows.drop(columns=["選取"])
                        final_save_df = final_save_df.iloc[:]
                        final_save_df.to_csv(temp_csv_path, mode='w', index=False, header=True, encoding='utf-8-sig')
                        st.session_state.save_success = f"🗑️ 成功刪除 {len(selected_rows)} 筆選取紀錄！"
                        st.rerun()
                    except Exception as e:
                        st.session_state.save_error = f"❌ 刪除時發生錯誤：{e}"
                        st.rerun()
        else:
            st.info("💡 目前暫存區尚無新輸入的資料，表單送出後將顯示在此。")

# ------------------ 底部區塊：資料呈現與報表 ------------------
st.markdown("---")
st.markdown("### 📑 藥品基本總表")
if not df_med_filtered.empty:
    st.dataframe(df_med_filtered, use_container_width=True, hide_index=True)
else:
    st.info("💡 找不到符合條件的藥品。")

st.markdown("---")
col_b1, col_b2 = st.columns([1, 1])

with col_b1:
    st.markdown("### 歷史進銷存")
    if not df_history_filtered.empty:
        st.dataframe(df_history_filtered, use_container_width=True, hide_index=True)
    else:
        st.info("💡 該篩選條件下無歷史進銷存紀錄。")
        
    st.markdown("### ⏳ 效期庫存總覽 (分品項+同效期加總)")
    if not df_expiry_filtered.empty:
        st.dataframe(df_expiry_filtered, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ 目前無效期庫存資料，或無符合篩選條件的品項。")

with col_b2:
    # ✨ VISUAL VISUAL: 近效品項區塊美化
    st.markdown("### 近效兩個月內品項")
    if not df_med_filtered.empty:
        df_near_expiry = df_med_filtered[df_med_filtered["近效未過期"] != '-'][
            ["六編/藥品簡稱", "藥品名稱", "類別", "近效未過期", "近效總量"]
        ]
    else:
        df_near_expiry = pd.DataFrame()
        
    if not df_near_expiry.empty:
        df_near_expiry = df_near_expiry.sort_values(by="近效未過期")
        st.warning(f"有 {len(df_near_expiry)} 筆品項正處於近效期狀態！")
        st.dataframe(df_near_expiry, use_container_width=True, hide_index=True)
    else:
        st.success("無近效品項")

    # ✨ VISUAL VISUAL: 安全量警示區塊美化
    st.markdown("### ⚠️ 庫存低於安全量品項")
    if not df_med_filtered.empty and "安全量" in df_med_filtered.columns:
        df_stock_warning = df_med_filtered.copy()
        df_stock_warning["未過期庫存"] = df_stock_warning["六編/藥品簡稱"].map(unexpired_stock_map).fillna(0)
        df_stock_warning["安全量_num"] = pd.to_numeric(df_stock_warning["安全量"], errors='coerce')
        df_stock_warning["未過期庫存_num"] = pd.to_numeric(df_stock_warning["未過期庫存"], errors='coerce')
        
        warning_cond = df_stock_warning["安全量_num"].notna() & (df_stock_warning["未過期庫存_num"] < df_stock_warning["安全量_num"])
        df_warning_show = df_stock_warning[warning_cond][
            ["六編/藥品簡稱", "藥品名稱", "安全量", "未過期庫存"]
        ]
    else:
        df_warning_show = pd.DataFrame()
        
    if not df_warning_show.empty:
        df_warning_show = df_warning_show.sort_values(by="未過期庫存")
        st.error(f" {len(df_warning_show)} 項藥品的「可用庫存」已低於安全量")
        st.dataframe(df_warning_show, use_container_width=True, hide_index=True)
    else:
        st.success("庫存均在安全量以上。")