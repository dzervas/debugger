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

#include "debugserversetting.h"

using namespace BinaryNinjaDebuggerAPI;
using namespace BinaryNinja;
using namespace std;

DebugServerSettingsDialog::DebugServerSettingsDialog(QWidget* parent, DebuggerControllerRef controller) :
	QDialog(), m_controller(controller)
{
	setWindowTitle("Debug Server Settings");
	setMinimumSize(UIContext::getScaledWindowSize(400, 130));
	setAttribute(Qt::WA_DeleteOnClose);

	setModal(true);
	QVBoxLayout* layout = new QVBoxLayout;
	layout->setSpacing(0);

	QHBoxLayout* titleLayout = new QHBoxLayout;
	titleLayout->setContentsMargins(0, 0, 0, 0);

	m_platformEntry = new QComboBox(this);
	auto platformsMetaData = m_controller->GetAdapterProperty("platforms");
	if (platformsMetaData && platformsMetaData->IsStringList())
	{
		auto platforms = platformsMetaData->GetStringList();
		for (const auto& platform : platforms)
			m_platformEntry->addItem(QString::fromStdString(platform));
	}

	auto currentPlatformMetadata = m_controller->GetAdapterProperty("current_platform");
	if (currentPlatformMetadata && currentPlatformMetadata->IsString())
	{
		const auto currentPlatform = currentPlatformMetadata->GetString();
		m_platformEntry->setCurrentText(QString::fromStdString(currentPlatform));
	}

	m_addressEntry = new QLineEdit(this);
	m_portEntry = new QLineEdit(this);

	QFormLayout* formLayout = new QFormLayout;
	formLayout->addRow("Platform", m_platformEntry);
	formLayout->addRow("Host", m_addressEntry);
	formLayout->addRow("Port", m_portEntry);

	QHBoxLayout* buttonLayout = new QHBoxLayout;
	buttonLayout->setContentsMargins(0, 0, 0, 0);

	QPushButton* cancelButton = new QPushButton("Cancel");
	connect(cancelButton, &QPushButton::clicked, [&]() { reject(); });
	QPushButton* acceptButton = new QPushButton("Accept");
	connect(acceptButton, &QPushButton::clicked, [&]() { apply(); });
	acceptButton->setDefault(true);

	buttonLayout->addStretch(1);
	buttonLayout->addWidget(cancelButton);
	buttonLayout->addWidget(acceptButton);

	layout->addLayout(titleLayout);
	layout->addSpacing(10);
	layout->addLayout(formLayout);
	layout->addStretch(1);
	layout->addSpacing(10);
	layout->addLayout(buttonLayout);
	setLayout(layout);

	m_addressEntry->setText(QString::fromStdString(m_controller->GetRemoteHost()));
	m_portEntry->setText(QString::number(m_controller->GetRemotePort()));
}


void DebugServerSettingsDialog::apply()
{
	std::string host = m_addressEntry->text().toStdString();
	m_controller->SetRemoteHost(host);
	Ref<Metadata> data = new Metadata(host);
	m_controller->GetData()->StoreMetadata("debugger.remote_host", data);

	std::string portString = m_portEntry->text().toStdString();
	uint64_t port;
	try
	{
		port = stoull(portString);
	}
	catch (const std::exception&)
	{
		port = 31337;
	}

	m_controller->SetRemotePort(port);
	data = new Metadata(port);
	m_controller->GetData()->StoreMetadata("debugger.remote_port", data);

	const auto platform = m_platformEntry->currentText().toStdString();
	if (!platform.empty())
	{
		data = new Metadata(platform);
		m_controller->SetAdapterProperty("current_platform", data);
		m_controller->GetData()->StoreMetadata("debugger.platform", data);
	}

	accept();
}
