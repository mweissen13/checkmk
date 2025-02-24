// Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
// This file is part of Checkmk (https://checkmk.com). It is subject to the
// terms and conditions defined in the file COPYING, which is part of this
// source code package.

#ifndef Attributes_h
#define Attributes_h

#include <string>
#include <unordered_map>

#include "livestatus/StringUtils.h"

using Attributes = std::unordered_map<std::string, std::string>;

enum class AttributeKind { custom_variables, tags, labels, label_sources };

inline std::tuple<AttributeKind, std::string> to_attribute_kind(
    const std::string &name) {
    if (mk::starts_with(name, "_TAG_")) {
        return {AttributeKind::tags, name.substr(5)};
    }
    if (mk::starts_with(name, "_LABEL_")) {
        return {AttributeKind::labels, name.substr(7)};
    }
    if (mk::starts_with(name, "_LABELSOURCE_")) {
        return {AttributeKind::label_sources, name.substr(13)};
    }
    return {AttributeKind::custom_variables, name};
}

#endif  // Attributes_h
