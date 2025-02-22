// Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#ifndef TableStatus_h
#define TableStatus_h

#include "config.h"  // IWYU pragma: keep

#include <string>

#include "Table.h"
#include "livestatus/Row.h"
#include "livestatus/global_counters.h"
class ColumnOffsets;
class MonitoringCore;
class Query;
class User;

class TableStatus : public Table {
public:
    explicit TableStatus(MonitoringCore *mc);

    [[nodiscard]] std::string name() const override;
    [[nodiscard]] std::string namePrefix() const override;
    void answerQuery(Query &query, const User &user) override;
    [[nodiscard]] Row getDefault() const override;

private:
    void addCounterColumns(const std::string &name,
                           const std::string &description,
                           const ColumnOffsets &offsets, Counter which);
};

#endif  // TableStatus_h
