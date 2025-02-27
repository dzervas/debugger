/*
Copyright 2020-2023 Vector 35 Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

#pragma once

#include <QDialog>
#include <QPushButton>
#include <QFormLayout>
#include <QAbstractItemModel>
#include <QItemSelectionModel>
#include <QModelIndex>
#include <QTableView>
#include <QHeaderView>
#include <QStyledItemDelegate>
#include "debuggerapi.h"
#include "ui.h"


class ProcessItem
{
private:
	uint32_t m_pid;
	std::string m_processName;

public:
	ProcessItem(uint32_t pid, std::string processName);
	uint32_t pid() const { return m_pid; }
	std::string processName() const { return m_processName; }
	bool operator==(const ProcessItem& other) const;
	bool operator!=(const ProcessItem& other) const;
	bool operator<(const ProcessItem& other) const;
};

Q_DECLARE_METATYPE(ProcessItem);


class ProcessListModel : public QAbstractTableModel
{
	Q_OBJECT;

protected:
	std::vector<ProcessItem> m_items;

public:
	enum ColumnHeaders
	{
		PidColumn,
		ProcessNameColumn,
	};

	ProcessListModel(QWidget* parent);
	virtual ~ProcessListModel();

	virtual QModelIndex index(int row, int col, const QModelIndex& parent = QModelIndex()) const override;

	virtual int rowCount(const QModelIndex& parent = QModelIndex()) const override
	{
		(void)parent;
		return (int)m_items.size();
	}
	virtual int columnCount(const QModelIndex& parent = QModelIndex()) const override
	{
		(void)parent;
		return 2;
	}
	ProcessItem getRow(int row) const;
	virtual QVariant data(const QModelIndex& i, int role) const override;
	virtual QVariant headerData(int column, Qt::Orientation orientation, int role) const override;
	virtual void sort(int col, Qt::SortOrder order) override;
	
	void updateRows(std::vector<DebugProcess> processList);
};


class ProcessItemDelegate : public QStyledItemDelegate
{
	Q_OBJECT;

	QFont m_font;
	int m_baseline, m_charWidth, m_charHeight, m_charOffset;

public:
	ProcessItemDelegate(QWidget* parent);
	void updateFonts();
	void paint(QPainter* painter, const QStyleOptionViewItem& option, const QModelIndex& idx) const;
	QSize sizeHint(const QStyleOptionViewItem& option, const QModelIndex& idx) const;
};


class ProcessListFilterProxyModel : public QSortFilterProxyModel
{
	Q_OBJECT;

public:
	ProcessListFilterProxyModel(QObject* parent);

protected:
	virtual bool filterAcceptsRow(int sourceRow, const QModelIndex& sourceParent) const override;
	virtual void sort(int col, Qt::SortOrder order) override;
};


class ProcessListWidget : public QTableView, public FilterTarget
{
	Q_OBJECT;

	DbgRef<DebuggerController> m_controller;

	ProcessListModel* m_model;
	ProcessItemDelegate* m_delegate;
	ProcessListFilterProxyModel* m_filter;

	UIActionHandler m_actionHandler;
	ContextMenuManager* m_contextMenuManager;
	Menu* m_menu;

	virtual void contextMenuEvent(QContextMenuEvent* event) override;

	virtual void setFilter(const std::string& filter) override;
	virtual void scrollToFirstItem() override;
	virtual void scrollToCurrentItem() override;
	virtual void selectFirstItem() override;
	virtual void activateFirstItem() override;

public:
	ProcessListWidget(QWidget* parent, DbgRef<DebuggerController> controller);
	~ProcessListWidget();

	uint32_t GetSelectedPid()
	{
		QModelIndexList sel = selectionModel()->selectedIndexes();
		if (sel.empty() || !sel[0].isValid())
			return 0;

		auto sourceIndex = m_filter->mapToSource(sel[0]);
		if (!sourceIndex.isValid())
			return 0;

		auto processItem = m_model->getRow(sourceIndex.row());
		return processItem.pid();
	}

	void updateColumnWidths();

public slots:
	void updateContent();
};


class AttachProcessDialog : public QDialog
{
	Q_OBJECT;

private:
	ProcessListWidget* m_processListWidget;
	FilteredView* m_filter;
	FilterEdit* m_separateEdit;
	uint32_t m_selectedPid {};

public:
	AttachProcessDialog(QWidget* parent, DbgRef<DebuggerController> controller);
	uint32_t GetSelectedPid();

private Q_SLOTS:
	void apply();
};
